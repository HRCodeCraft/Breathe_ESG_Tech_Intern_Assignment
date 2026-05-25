from django.contrib import admin
from .models import IngestionRun, RawRecord


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'source_type', 'status', 'organization', 'uploaded_by', 'uploaded_at', 'success_count', 'error_count']
    list_filter = ['source_type', 'status', 'organization']
    readonly_fields = ['uploaded_at', 'completed_at', 'error_log']


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ['run', 'row_number', 'parse_status']
    list_filter = ['parse_status']
    readonly_fields = ['raw_data']
