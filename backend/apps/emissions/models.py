import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.organizations.models import Organization
from apps.ingestion.models import IngestionRun, RawRecord


class EmissionRecord(models.Model):
    """
    Normalized, canonical emission record. One row = one measurable activity event.

    Key invariants:
    - quantity_normalized is always in the canonical unit for the category
      (kWh for electricity, litres for liquid fuels, km for travel, kg for solids)
    - co2e_kg = quantity_normalized * emission_factor
    - source_hash is a SHA-256 of (org, source_type, activity_date, facility, quantity, unit)
      used to detect duplicate uploads before creating a new record
    - original_values is a JSON snapshot captured at first edit, enabling diff display
    """

    class Scope(models.IntegerChoices):
        SCOPE_1 = 1, 'Scope 1 — Direct emissions'
        SCOPE_2 = 2, 'Scope 2 — Purchased electricity'
        SCOPE_3 = 3, 'Scope 3 — Value chain'

    class Category(models.TextChoices):
        # Scope 1
        STATIONARY_COMBUSTION = 'stationary_combustion', 'Stationary Combustion'
        MOBILE_COMBUSTION = 'mobile_combustion', 'Mobile Combustion'
        # Scope 2
        PURCHASED_ELECTRICITY = 'purchased_electricity', 'Purchased Electricity'
        # Scope 3
        BUSINESS_TRAVEL_AIR = 'business_travel_air', 'Business Travel — Flights'
        BUSINESS_TRAVEL_HOTEL = 'business_travel_hotel', 'Business Travel — Hotels'
        BUSINESS_TRAVEL_GROUND = 'business_travel_ground', 'Business Travel — Ground'
        PROCUREMENT = 'procurement', 'Purchased Goods & Services'
        WASTE = 'waste', 'Waste'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        FLAGGED = 'flagged', 'Flagged'
        REJECTED = 'rejected', 'Rejected'

    class Flag(models.TextChoices):
        OUTLIER = 'outlier', 'Statistical Outlier'
        DUPLICATE = 'duplicate', 'Possible Duplicate'
        MISSING_FACTOR = 'missing_factor', 'No Emission Factor Found'
        UNIT_MISMATCH = 'unit_mismatch', 'Unexpected Unit'
        FUTURE_DATE = 'future_date', 'Activity Date in Future'
        ZERO_VALUE = 'zero_value', 'Zero or Negative Quantity'
        INCOMPLETE = 'incomplete', 'Required Field Missing'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='emission_records')

    # Provenance — where did this row come from?
    ingestion_run = models.ForeignKey(
        IngestionRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='emission_records'
    )
    raw_record = models.OneToOneField(
        RawRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='emission_record'
    )
    source_hash = models.CharField(max_length=64, db_index=True)

    # GHG classification
    scope = models.IntegerField(choices=Scope.choices)
    category = models.CharField(max_length=40, choices=Category.choices)
    subcategory = models.CharField(max_length=100, blank=True)

    # Activity timing
    activity_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)  # for utility billing periods
    period_end = models.DateField(null=True, blank=True)

    # Activity context
    facility = models.CharField(max_length=255, blank=True)   # plant/site/cost centre
    cost_center = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    # Raw quantity as it came in
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    unit = models.CharField(max_length=30)

    # Normalized quantity (canonical unit for category)
    quantity_normalized = models.DecimalField(max_digits=18, decimal_places=6)
    unit_normalized = models.CharField(max_length=30)

    # Emission calculation
    emission_factor = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=100, blank=True)
    emission_factor_unit = models.CharField(max_length=50, blank=True)
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    co2_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    ch4_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    n2o_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    # Review workflow
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    flags = models.JSONField(default=list)  # list of Flag values
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Edit tracking
    is_edited = models.BooleanField(default=False)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='edited_records'
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    original_values = models.JSONField(null=True, blank=True)  # snapshot on first edit

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'scope', 'activity_date']),
            models.Index(fields=['source_hash']),
        ]

    def __str__(self):
        return f"{self.category} {self.activity_date} {self.co2e_kg}kgCO2e"

    @property
    def co2e_tonnes(self):
        if self.co2e_kg is not None:
            return self.co2e_kg / Decimal('1000')
        return None


class EmissionFactor(models.Model):
    """
    Reference table of emission factors.
    Source: UK DEFRA GHG Conversion Factors 2024, US EPA eGRID 2023.
    Versioned so we can track which factor vintage was used per record.
    """

    class FactorSource(models.TextChoices):
        DEFRA_2024 = 'DEFRA_2024', 'UK DEFRA 2024'
        EPA_2023 = 'EPA_2023', 'US EPA eGRID 2023'
        IPCC_AR6 = 'IPCC_AR6', 'IPCC AR6'
        GHG_PROTOCOL = 'GHG_PROTOCOL', 'GHG Protocol'

    category = models.CharField(max_length=40)
    subcategory = models.CharField(max_length=100, blank=True)
    fuel_type = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=30)
    co2e_per_unit = models.DecimalField(max_digits=18, decimal_places=8)
    co2_per_unit = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    ch4_per_unit = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    n2o_per_unit = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_source = models.CharField(max_length=30, choices=FactorSource.choices)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['category', 'subcategory']

    def __str__(self):
        return f"{self.subcategory or self.category} — {self.co2e_per_unit} kgCO2e/{self.unit}"


class UnitConversion(models.Model):
    """Lookup for normalising all the ways SAP and utilities express the same thing."""
    from_unit = models.CharField(max_length=30, unique=True)
    to_unit = models.CharField(max_length=30)
    multiplier = models.DecimalField(max_digits=20, decimal_places=10)
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.from_unit} → {self.to_unit} (×{self.multiplier})"


class AirportCode(models.Model):
    """IATA airport lookup used to compute great-circle distance for flight emissions."""
    iata = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.iata} — {self.name}"
