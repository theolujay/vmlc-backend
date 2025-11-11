# comms/models.py

from django.db import models
from django.contrib.postgres.fields import ArrayField
from vmlc.models import Staff, Candidate, User


class Broadcast(models.Model):
    class Mediums(models.TextChoices):
        PLATFORM = "platform", "Platform"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        FAILED_TO_QUEUE = "failed_to_queue", "Failed to Queue"
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Partial Success"
        FAILED = "failed", "Failed"

    id = models.AutoField(primary_key=True)
    subject = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broadcasts",
    )
    mediums = ArrayField(
        models.CharField(max_length=20, choices=Mediums.choices),
        default=list,
        help_text="List of mediums to use (Email, SMS, Platform, etc.)",
    )
    target_roles = ArrayField(
        models.CharField(max_length=20, choices=Candidate.Roles.choices),
        default=list,
        help_text="List of target roles to broadcast to (Screening, League, Final, Winner)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Overall broadcast status",
    )
    last_attempt = models.DateTimeField(null=True, blank=True)
    task_id = models.CharField(
        max_length=255, null=True, blank=True, help_text="Celery task ID for tracking"
    )

    def __str__(self):
        mediums = ", ".join(self.mediums)
        target_roles = ", ".join(self.target_roles)
        return f"{self.subject} [{mediums}] -> [{target_roles}] ({self.status})"


class BroadcastLog(models.Model):
    class MediumStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.AutoField(primary_key=True)
    broadcast = models.ForeignKey(
        Broadcast, related_name="logs", on_delete=models.CASCADE
    )
    medium = models.CharField(max_length=20, choices=Broadcast.Mediums.choices)
    target_role = models.CharField(max_length=20, choices=Candidate.Roles.choices)
    status = models.CharField(
        max_length=20,
        choices=MediumStatus.choices,
        default=MediumStatus.PENDING,
    )
    message = models.TextField(blank=True, help_text="Error or status message")
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.broadcast.subject} [{self.medium} -> {self.target_role}] {self.status}"


class Notification(models.Model):
    """
    Represents a real-time notification sent to a user.
    """

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    subject = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.recipient.email}: {self.subject}"
