from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['action']
    ordering = ['-timestamp']

    def get_queryset(self):
        qs = AuditEvent.objects.filter(
            organization=self.request.user.organization
        ).select_related('user')

        record_id = self.request.query_params.get('emission_record')
        if record_id:
            qs = qs.filter(emission_record_id=record_id)

        run_id = self.request.query_params.get('ingestion_run')
        if run_id:
            qs = qs.filter(ingestion_run_id=run_id)

        return qs
