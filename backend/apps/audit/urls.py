from django.urls import path
from .views import AuditEventListView

urlpatterns = [
    path('audit/', AuditEventListView.as_view(), name='audit-list'),
]
