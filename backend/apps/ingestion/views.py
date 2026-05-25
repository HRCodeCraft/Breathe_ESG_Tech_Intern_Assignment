from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import IngestionRun
from .serializers import IngestionRunSerializer, IngestionUploadSerializer
from .pipeline import run_ingestion


class IngestionRunListView(generics.ListAPIView):
    serializer_class = IngestionRunSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['source_type', 'status']

    def get_queryset(self):
        return IngestionRun.objects.filter(
            organization=self.request.user.organization
        ).select_related('uploaded_by')


class IngestionUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = IngestionUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data['file']
        source_type = serializer.validated_data['source_type']

        # Read bytes before Django's storage consumes the stream
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

        run = IngestionRun.objects.create(
            organization=request.user.organization,
            source_type=source_type,
            uploaded_by=request.user,
            file_name=uploaded_file.name,
            raw_file=uploaded_file,
        )
        try:
            run = run_ingestion(run, file_bytes, request.user)
        except Exception as e:
            run.status = IngestionRun.Status.FAILED
            run.error_log = [{'error': str(e)}]
            run.save()

        return Response(IngestionRunSerializer(run).data, status=status.HTTP_201_CREATED)


class IngestionRunDetailView(generics.RetrieveAPIView):
    serializer_class = IngestionRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IngestionRun.objects.filter(organization=self.request.user.organization)
