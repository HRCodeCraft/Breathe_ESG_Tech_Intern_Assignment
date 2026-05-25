from rest_framework import serializers
from .models import IngestionRun, RawRecord


class IngestionRunSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = IngestionRun
        fields = [
            'id', 'source_type', 'source_type_display', 'status', 'status_display',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at', 'completed_at',
            'file_name', 'row_count', 'success_count', 'error_count', 'skipped_count',
            'error_log',
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None


class IngestionUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    source_type = serializers.ChoiceField(choices=IngestionRun.SourceType.choices)
