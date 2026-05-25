from django.urls import path
from .views import IngestionRunListView, IngestionUploadView, IngestionRunDetailView

urlpatterns = [
    path('ingestion/', IngestionRunListView.as_view(), name='ingestion-list'),
    path('ingestion/upload/', IngestionUploadView.as_view(), name='ingestion-upload'),
    path('ingestion/<uuid:pk>/', IngestionRunDetailView.as_view(), name='ingestion-detail'),
]
