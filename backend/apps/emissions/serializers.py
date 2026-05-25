from rest_framework import serializers
from .models import EmissionRecord


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    co2e_tonnes = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    source_type = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'scope_display', 'category', 'category_display',
            'subcategory', 'activity_date', 'period_start', 'period_end',
            'facility', 'cost_center', 'supplier', 'description',
            'quantity', 'unit', 'quantity_normalized', 'unit_normalized',
            'emission_factor', 'emission_factor_source', 'emission_factor_unit',
            'co2e_kg', 'co2e_tonnes', 'co2_kg', 'ch4_kg', 'n2o_kg',
            'status', 'status_display', 'flags',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at', 'review_notes',
            'is_edited', 'original_values',
            'ingestion_run', 'source_type',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'scope', 'category', 'subcategory', 'quantity', 'unit',
            'quantity_normalized', 'unit_normalized', 'emission_factor',
            'emission_factor_source', 'co2e_kg', 'co2e_tonnes',
            'co2_kg', 'ch4_kg', 'n2o_kg', 'is_edited', 'original_values',
            'ingestion_run', 'source_type', 'created_at', 'updated_at',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_source_type(self, obj):
        if obj.ingestion_run:
            return obj.ingestion_run.source_type
        return None


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    """For analyst edits — only a limited set of fields are writable."""

    class Meta:
        model = EmissionRecord
        fields = ['facility', 'cost_center', 'supplier', 'description',
                  'review_notes', 'activity_date']

    def update(self, instance, validated_data):
        from django.utils import timezone
        # Snapshot original values on first edit
        if not instance.is_edited:
            instance.original_values = {
                'facility': instance.facility,
                'cost_center': instance.cost_center,
                'supplier': instance.supplier,
                'description': instance.description,
                'activity_date': instance.activity_date.isoformat(),
            }
        instance.is_edited = True
        instance.edited_by = self.context['request'].user
        instance.edited_at = timezone.now()
        return super().update(instance, validated_data)


class BulkActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    action = serializers.ChoiceField(choices=['approve', 'flag', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')
