"""
Models backing the OpenAPI "External" endpoints (e.g. user reports, wide alerts).
"""

from __future__ import annotations

import uuid

from django.db import models


class WideAlert(models.Model):
    """Country-wide/public alert.

    Maps to OpenAPI schema `WideAlerts`.
    """

    id = models.BigAutoField(primary_key=True)
    alert_id = models.CharField(max_length=255, unique=True)
    alert_header = models.CharField(max_length=255)
    alert_description = models.TextField()
    alert_url = models.URLField(blank=True, null=True)
    timestamp = models.DateTimeField()
    source = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return self.alert_id


class UserData(models.Model):
    """Minimal user data record.
    Maps to OpenAPI schema `UserData`.
    """
    id = models.BigAutoField(primary_key=True)
    user_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self) -> str:
        return self.user_id


class UserReport(models.Model):
    """User-originated report.
    Maps to OpenAPI schemas `UserReportCreate` (POST input) and `UserReports`
    (GET output).
    """

    STATUS_PENDING = "pending"
    STATUS_REVIEWED = "reviewed"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = (
        (STATUS_PENDING, "pending"),
        (STATUS_REVIEWED, "reviewed"),
        (STATUS_RESOLVED, "resolved"),
    )

    id = models.BigAutoField(primary_key=True)
    report_id = models.CharField(max_length=32, unique=True, editable=False)
    user_id = models.CharField(max_length=255, blank=True, null=True)
    report_type = models.CharField(max_length=255)

    location_stop_id = models.CharField(max_length=255, blank=True, null=True)
    location_lat = models.FloatField(blank=True, null=True)
    location_lon = models.FloatField(blank=True, null=True)

    description = models.CharField(max_length=500)
    user_evidence = models.JSONField(blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        # Assign a human-readable public ID on first save (used for API responses and logs)
        if not self.report_id:
            self.report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.report_id
