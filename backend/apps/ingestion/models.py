import uuid
from django.db import models
from django.conf import settings
from apps.organizations.models import Organization


class IngestionRun(models.Model):
    """One file upload / API pull event. Immutable once completed."""

    class SourceType(models.TextChoices):
        SAP_FUEL = 'sap_fuel', 'SAP Fuel & Combustion'
        SAP_PROCUREMENT = 'sap_procurement', 'SAP Procurement'
        UTILITY_ELECTRICITY = 'utility_electricity', 'Utility Electricity'
        TRAVEL = 'travel', 'Corporate Travel'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        COMPLETED_WITH_ERRORS = 'completed_with_errors', 'Completed with Errors'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ingestion_runs')
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='uploads'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    file_name = models.CharField(max_length=255)
    raw_file = models.FileField(upload_to='ingestion/raw/', null=True, blank=True)

    row_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)

    # JSON array of {row, error_type, message, raw_data}
    error_log = models.JSONField(default=list)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.source_type} — {self.file_name} ({self.status})"


class RawRecord(models.Model):
    """Verbatim copy of each parsed row, preserved for traceability."""

    class ParseStatus(models.TextChoices):
        OK = 'ok', 'OK'
        ERROR = 'error', 'Error'
        SKIPPED = 'skipped', 'Skipped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name='raw_records')
    row_number = models.IntegerField()
    raw_data = models.JSONField()
    parse_status = models.CharField(max_length=10, choices=ParseStatus.choices, default=ParseStatus.OK)
    parse_error = models.TextField(blank=True)

    class Meta:
        ordering = ['run', 'row_number']
        unique_together = [('run', 'row_number')]
