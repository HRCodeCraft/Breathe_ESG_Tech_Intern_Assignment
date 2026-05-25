import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    """Tenant. Every piece of data is scoped to an org."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    industry = models.CharField(max_length=100, blank=True)
    reporting_year = models.PositiveSmallIntegerField(default=2024)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        ANALYST = 'analyst', 'Analyst'
        AUDITOR = 'auditor', 'Auditor (read-only)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='users', null=True, blank=True
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ANALYST)

    def __str__(self):
        return f"{self.username} ({self.organization})"
