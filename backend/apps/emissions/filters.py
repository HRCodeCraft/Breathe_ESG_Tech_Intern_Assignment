import django_filters
from .models import EmissionRecord


class EmissionRecordFilter(django_filters.FilterSet):
    scope = django_filters.NumberFilter()
    category = django_filters.CharFilter()
    status = django_filters.CharFilter()
    facility = django_filters.CharFilter(lookup_expr='icontains')
    supplier = django_filters.CharFilter(lookup_expr='icontains')
    activity_date_after = django_filters.DateFilter(field_name='activity_date', lookup_expr='gte')
    activity_date_before = django_filters.DateFilter(field_name='activity_date', lookup_expr='lte')
    ingestion_run = django_filters.UUIDFilter()
    has_flags = django_filters.BooleanFilter(method='filter_has_flags')

    class Meta:
        model = EmissionRecord
        fields = ['scope', 'category', 'status', 'facility', 'supplier',
                  'activity_date_after', 'activity_date_before', 'ingestion_run']

    def filter_has_flags(self, queryset, name, value):
        if value:
            return queryset.exclude(flags=[])
        return queryset.filter(flags=[])
