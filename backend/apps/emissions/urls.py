from django.urls import path
from .views import (
    EmissionRecordListView, EmissionRecordDetailView,
    RecordApproveView, RecordFlagView, BulkActionView, DashboardSummaryView,
)

urlpatterns = [
    path('emissions/', EmissionRecordListView.as_view(), name='emission-list'),
    path('emissions/<uuid:pk>/', EmissionRecordDetailView.as_view(), name='emission-detail'),
    path('emissions/<uuid:pk>/approve/', RecordApproveView.as_view(), name='emission-approve'),
    path('emissions/<uuid:pk>/flag/', RecordFlagView.as_view(), name='emission-flag'),
    path('emissions/bulk/', BulkActionView.as_view(), name='emission-bulk'),
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
]
