from django.db import models
from django.contrib.postgres.fields import ArrayField
from identity.models import Staff, Candidate, User


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
    target_roles = models.JSONField(
        default=dict,
        help_text="""
        Dictionary of target roles to broadcast to:
        {
            "staff": ["volunteer", "moderator", "admin", "manager", "superadmin"],
            "candidate": ["screening", "league", "final", "winner"]
        }
        """,
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

        target_parts = []
        if self.target_roles.get("staff"):
            target_parts.append(f"Staff: {', '.join(self.target_roles['staff'])}")
        if self.target_roles.get("candidate"):
            target_parts.append(
                f"Candidate: {', '.join(self.target_roles['candidate'])}"
            )
        target_roles = " | ".join(target_parts) if target_parts else "No targets"

        return f"{self.subject} [{mediums}] -> [{target_roles}] ({self.status})"

    def clean(self):
        """Validation for target_roles structure"""
        from django.core.exceptions import ValidationError

        if not isinstance(self.target_roles, dict):
            raise ValidationError("target_roles must be a dictionary")

        # Validate that keys are either 'staff' or 'candidate'
        valid_keys = {"staff", "candidate"}
        invalid_keys = set(self.target_roles.keys()) - valid_keys
        if invalid_keys:
            raise ValidationError(f"Invalid keys in target_roles: {invalid_keys}")

        # Validate staff roles
        if "staff" in self.target_roles:
            valid_staff_roles = [choice[0] for choice in Staff.Roles.choices]
            invalid = set(self.target_roles["staff"]) - set(valid_staff_roles)
            if invalid:
                raise ValidationError(f"Invalid staff roles: {invalid}")

        # Validate candidate roles
        if "candidate" in self.target_roles:
            valid_candidate_roles = [choice[0] for choice in Candidate.Roles.choices]
            invalid = set(self.target_roles["candidate"]) - set(valid_candidate_roles)
            if invalid:
                raise ValidationError(f"Invalid candidate roles: {invalid}")
    class Meta:
        verbose_name = "Broadcast"
        verbose_name_plural = "Broadcasts"

class BroadcastLog(models.Model):
    class MediumStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    COMBINED_ROLE_CHOICES = list(Candidate.Roles.choices) + list(Staff.Roles.choices)

    id = models.AutoField(primary_key=True)
    broadcast = models.ForeignKey(
        Broadcast, related_name="logs", on_delete=models.CASCADE
    )
    medium = models.CharField(max_length=20, choices=Broadcast.Mediums.choices)
    target_role = models.CharField(max_length=20, choices=COMBINED_ROLE_CHOICES)
    role_type = models.CharField(
        max_length=10,
        default="candidate",
        choices=[("staff", "Staff"), ("candidate", "Candidate")],
        help_text="Whether this is a staff or candidate role",
    )
    status = models.CharField(
        max_length=20,
        choices=MediumStatus.choices,
        default=MediumStatus.PENDING,
    )
    message = models.TextField(blank=True, help_text="Error or status message")
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.broadcast.subject} [{self.medium} -> {self.role_type}:{self.target_role}] {self.status}"

    class Meta:
        verbose_name = "Broadcast Log"
        verbose_name_plural = "Broadcast Logs"

class Notification(models.Model):
    """
    Represents a real-time notification sent to a user.
    """

    class Type(models.TextChoices):
        ALERT = "alert", "Alert"
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    subject = models.CharField(max_length=100)
    message = models.TextField()
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.ALERT, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read_by_recipient = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.recipient.email}: {self.subject}"


class BackupLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FIRST_FAILURE = "first_failure", "First Failure"
        FINAL_FAILURE = "final_failure", "Final Failure"
        SUCCESS_AFTER_RETRY = "success_after_retry", "Success After Retry"

    class Environment(models.TextChoices):
        PRODUCTION = "prod", "Production"
        STAGING = "staging", "Staging"

    status = models.CharField(max_length=30, choices=Status.choices)
    environment = models.CharField(max_length=10, choices=Environment.choices)
    timestamp = models.DateTimeField()
    backup_filename = models.CharField(max_length=255)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Backup Log"
        verbose_name_plural = "Backup Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"BackupLog for {self.environment} at {self.timestamp}: {self.status}"
