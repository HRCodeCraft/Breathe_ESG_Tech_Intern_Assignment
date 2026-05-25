from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'organization', 'timestamp']
    list_filter = ['action', 'organization']
    readonly_fields = ['id', 'organization', 'user', 'action', 'timestamp',
                       'emission_record_id', 'ingestion_run_id',
                       'before_state', 'after_state', 'metadata', 'ip_address']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
