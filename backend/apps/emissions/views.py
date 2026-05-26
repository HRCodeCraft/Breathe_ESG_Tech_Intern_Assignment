from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import EmissionRecord
from .serializers import EmissionRecordSerializer, EmissionRecordUpdateSerializer, BulkActionSerializer
from .filters import EmissionRecordFilter
from apps.audit.models import AuditEvent


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class EmissionRecordListView(generics.ListAPIView):
    serializer_class = EmissionRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = EmissionRecordFilter
    ordering_fields = ['activity_date', 'co2e_kg', 'created_at', 'status']
    ordering = ['-activity_date']
    search_fields = ['facility', 'supplier', 'description', 'subcategory']

    def get_queryset(self):
        return EmissionRecord.objects.filter(
            organization=self.request.user.organization
        ).select_related('reviewed_by', 'ingestion_run', 'edited_by')


class EmissionRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return EmissionRecordUpdateSerializer
        return EmissionRecordSerializer

    def get_queryset(self):
        return EmissionRecord.objects.filter(organization=self.request.user.organization)

    def perform_update(self, serializer):
        before = EmissionRecordSerializer(serializer.instance).data
        instance = serializer.save()
        AuditEvent.objects.create(
            organization=self.request.user.organization,
            user=self.request.user,
            action=AuditEvent.Action.RECORD_EDITED,
            emission_record_id=instance.id,
            before_state=before,
            after_state=EmissionRecordSerializer(instance).data,
            ip_address=_get_client_ip(self.request),
        )


class RecordApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk, organization=request.user.organization)
        except EmissionRecord.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        before_status = record.status
        record.status = EmissionRecord.Status.APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = request.data.get('notes', '')
        record.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

        AuditEvent.objects.create(
            organization=request.user.organization,
            user=request.user,
            action=AuditEvent.Action.RECORD_APPROVED,
            emission_record_id=record.id,
            before_state={'status': before_status},
            after_state={'status': record.status},
            ip_address=_get_client_ip(request),
        )
        return Response(EmissionRecordSerializer(record).data)


class RecordFlagView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk, organization=request.user.organization)
        except EmissionRecord.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        before_status = record.status
        record.status = EmissionRecord.Status.FLAGGED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = request.data.get('notes', '')
        record.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

        AuditEvent.objects.create(
            organization=request.user.organization,
            user=request.user,
            action=AuditEvent.Action.RECORD_FLAGGED,
            emission_record_id=record.id,
            before_state={'status': before_status},
            after_state={'status': record.status},
            ip_address=_get_client_ip(request),
        )
        return Response(EmissionRecordSerializer(record).data)


class BulkActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BulkActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ids = serializer.validated_data['ids']
        action = serializer.validated_data['action']
        notes = serializer.validated_data['notes']

        records = EmissionRecord.objects.filter(
            id__in=ids, organization=request.user.organization
        )

        status_map = {
            'approve': EmissionRecord.Status.APPROVED,
            'flag': EmissionRecord.Status.FLAGGED,
            'reject': EmissionRecord.Status.REJECTED,
        }
        new_status = status_map[action]
        count = records.count()

        records.update(
            status=new_status,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            review_notes=notes,
        )

        audit_action_map = {
            'approve': AuditEvent.Action.BULK_APPROVED,
            'flag': AuditEvent.Action.BULK_FLAGGED,
            'reject': AuditEvent.Action.BULK_FLAGGED,
        }
        AuditEvent.objects.create(
            organization=request.user.organization,
            user=request.user,
            action=audit_action_map[action],
            metadata={'count': count, 'ids': [str(i) for i in ids], 'notes': notes},
            ip_address=_get_client_ip(request),
        )
        return Response({'updated': count})


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        qs = EmissionRecord.objects.filter(organization=org)

        # Scope totals (approved records only for final numbers, all for pending view)
        approved_qs = qs.filter(status=EmissionRecord.Status.APPROVED)

        scope_totals = {}
        for scope in [1, 2, 3]:
            agg = approved_qs.filter(scope=scope).aggregate(total=Sum('co2e_kg'))
            scope_totals[f'scope_{scope}_co2e_kg'] = agg['total'] or Decimal('0')

        total_co2e = sum(scope_totals.values())

        # Category breakdown
        category_data = list(
            approved_qs.values('category').annotate(total=Sum('co2e_kg')).order_by('-total')
        )

        # Status counts
        status_counts = {}
        for s in EmissionRecord.Status.values:
            status_counts[s] = qs.filter(status=s).count()

        # Flag counts
        flagged_count = qs.exclude(flags=[]).count()

        # Recent ingestion runs
        from apps.ingestion.models import IngestionRun
        from apps.ingestion.serializers import IngestionRunSerializer
        recent_runs = IngestionRun.objects.filter(organization=org)[:5]

        # Monthly trend (last 12 months, approved records)
        from django.db.models.functions import TruncMonth
        monthly = list(
            approved_qs.annotate(month=TruncMonth('activity_date'))
            .values('month', 'scope')
            .annotate(total=Sum('co2e_kg'))
            .order_by('month', 'scope')
        )

        return Response({
            'scope_totals': scope_totals,
            'total_co2e_kg': total_co2e,
            'total_co2e_tonnes': total_co2e / Decimal('1000'),
            'category_breakdown': category_data,
            'status_counts': status_counts,
            'flagged_count': flagged_count,
            'total_records': qs.count(),
            'approved_records': approved_qs.count(),
            'pending_records': qs.filter(status=EmissionRecord.Status.PENDING).count(),
            'monthly_trend': monthly,
            'recent_runs': IngestionRunSerializer(recent_runs, many=True).data,
        })
