import uuid
from django.db import models
from django.conf import settings
from apps.organizations.models import Organization


class AuditEvent(models.Model):
    """
    Immutable, append-only audit trail.
    Never updated after creation — before_state/after_state are JSON snapshots.
    """

    class Action(models.TextChoices):
        RECORD_CREATED = 'record_created', 'Record Created'
        RECORD_EDITED = 'record_edited', 'Record Edited'
        RECORD_APPROVED = 'record_approved', 'Record Approved'
        RECORD_FLAGGED = 'record_flagged', 'Record Flagged'
        RECORD_REJECTED = 'record_rejected', 'Record Rejected'
        BULK_APPROVED = 'bulk_approved', 'Bulk Approved'
        BULK_FLAGGED = 'bulk_flagged', 'Bulk Flagged'
        RUN_STARTED = 'run_started', 'Ingestion Run Started'
        RUN_COMPLETED = 'run_completed', 'Ingestion Run Completed'
        RUN_FAILED = 'run_failed', 'Ingestion Run Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='audit_events')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_events'
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    timestamp = models.DateTimeField(auto_now_add=True)

    # Polymorphic target — either an emission record or an ingestion run
    emission_record_id = models.UUIDField(null=True, blank=True, db_index=True)
    ingestion_run_id = models.UUIDField(null=True, blank=True, db_index=True)

    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict)  # e.g. {"count": 47} for bulk actions

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        # No update/delete permissions should be granted on this table in prod
        default_permissions = ('add', 'view')

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"
