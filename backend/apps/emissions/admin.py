from django.contrib import admin
from .models import EmissionRecord, EmissionFactor, UnitConversion, AirportCode


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['organization', 'scope', 'category', 'activity_date', 'co2e_kg', 'status', 'flags']
    list_filter = ['scope', 'category', 'status', 'organization']
    readonly_fields = ['source_hash', 'created_at', 'updated_at', 'original_values']
    search_fields = ['facility', 'supplier', 'description']


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ['category', 'subcategory', 'unit', 'co2e_per_unit', 'factor_source', 'valid_from']
    list_filter = ['category', 'factor_source']


@admin.register(UnitConversion)
class UnitConversionAdmin(admin.ModelAdmin):
    list_display = ['from_unit', 'to_unit', 'multiplier', 'notes']


@admin.register(AirportCode)
class AirportCodeAdmin(admin.ModelAdmin):
    list_display = ['iata', 'name', 'city', 'country']
    search_fields = ['iata', 'name', 'city']
