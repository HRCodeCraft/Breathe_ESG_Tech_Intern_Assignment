from rest_framework import serializers
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'action', 'action_display', 'timestamp',
            'user', 'user_name',
            'emission_record_id', 'ingestion_run_id',
            'before_state', 'after_state', 'metadata',
        ]

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'System'
