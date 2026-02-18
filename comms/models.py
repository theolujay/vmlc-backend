import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models

from identity.models import Candidate, Staff, User

# TODO: move to [core] app
phone_regex = RegexValidator(
    regex=r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$",
    message="Phone number must be in format: '+234XXXXXXXXXX' or '0XXXXXXXXXX'",
)


# ---------------------------------------------------------------------------
# Public / Unauthenticated
# ---------------------------------------------------------------------------
class PublicSupportRequest(models.Model):
    """
    Captures support inquiries submitted by unauthenticated (public) users,
    from the Verboheit landing page (https://verboheit.org/support-us).

    Intended for sponsorship, partnership, media, and general enquiries where
    the submitter does not have a platform account.
    """

    class Type(models.TextChoices):
        SPONSORSHIP = "sponsorship", "Sponsorship"
        PARTNERSHIP = "partnership", "Partnership"
        MEDIA_SUPPORT = "media_publiciy", "Media/Publicity"
        OTHER = "other", "Other"

    email = models.EmailField()
    full_name = models.CharField(max_length=255)
    organization = models.CharField(max_length=255, blank=True)
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        help_text="Nigerian phone number.",
        blank=True,
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    message = models.TextField(help_text="Message from the user.")
    consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Public Support Request"
        verbose_name_plural = "Public Support Requests"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.type}) - {self.organization}"


# ---------------------------------------------------------------------------
# Support Ticketing
# ---------------------------------------------------------------------------
class SupportTicket(models.Model):
    """
    Represents an authenticated support conversation between a user and staff.

    Tickets progress through statuses (Open → In Progress → Resolved) and can
    be assigned to a specific staff member. Each ticket contains one or more
    TicketMessage records. Deletion is soft — records are flagged with
    is_deleted rather than removed from the database.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    user = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
        help_text="Authenticated user who submitted the ticket, if applicable.",
    )
    assigned_to = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    message = models.TextField(help_text="Initial message from the user.")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    is_deleted = models.BooleanField(default=False)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_to"]),
        ]

    def __str__(self) -> str:
        actor = self.user.email if self.user else "Anonymous"
        return f"{actor} - {self.status}"

    def delete(self, *args, **kwargs) -> None:
        """Soft-delete: marks the ticket as deleted instead of removing it."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])


class TicketMessage(models.Model):
    """
    An individual message within a SupportTicket conversation.

    Messages are immutable once created — save() is intentionally
    restricted to new instances only. When a new message is saved, the parent
    ticket's last_message_at timestamp is updated atomically.

    Supports text, image, and file attachment types. System-generated messages
    (e.g. status changes) use MessageType.SYSTEM.
    """

    class SenderType(models.TextChoices):
        CANDIDATE = "user", "Candidate"
        STAFF = "staff", "Staff"
        SYSTEM = "system", "System"

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        FILE = "file", "File"
        SYSTEM = "system", "System"

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_support_messages",
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    text = models.TextField()
    attachment = models.FileField(
        upload_to="support_attachments/",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
        ]

    def __str__(self) -> str:
        actor = self.sender.email if self.sender else "System"
        return f"{actor} - {self.created_at}"

    @property
    def sender_type(self) -> str:
        """
        Derives sender type from the related User instance.

        Returns 'staff' when the sender has an associated Staff
        profile, otherwise 'candidate'.
        """
        if self.sender and hasattr(self.sender, "staff_profile"):
            return self.SenderType.STAFF
        return self.SenderType.CANDIDATE

    def save(self, *args, **kwargs) -> None:
        """
        Persists the message and, on creation, updates the parent ticket's
        last_message_at field via a single atomic UPDATE query.
        """
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            SupportTicket.objects.filter(pk=self.ticket_id).update(
                last_message_at=self.created_at
            )


class MessageRead(models.Model):
    """
    Tracks which users have read a given TicketMessage.

    Used to drive unread-message indicators in the support UI.
    """

    message = models.ForeignKey(
        "TicketMessage",
        on_delete=models.CASCADE,
        related_name="reads",
    )
    user = models.ForeignKey("identity.User", on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")
        indexes = [
            models.Index(fields=["user"]),
        ]


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------
class Broadcast(models.Model):
    """
    Represents a mass message dispatched to one or more target role groups
    across one or more delivery mediums (Email, SMS, Platform, WhatsApp).

    The target_roles JSON field specifies which staff or candidate roles
    should receive the message. Validation is enforced via clean().

    Broadcasts are executed asynchronously via Celery; task_id stores the
    Celery task identifier for monitoring. BroadcastLog records are created
    per medium-role combination to track individual delivery outcomes.
    """

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
    created_by = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broadcasts",
    )
    subject = models.CharField(max_length=100)
    message = models.TextField()
    mediums = ArrayField(
        models.CharField(max_length=20, choices=Mediums.choices),
        default=list,
        help_text="Ordered list of delivery mediums (Email, SMS, Platform, WhatsApp).",
    )
    target_roles = models.JSONField(
        default=dict,
        help_text=(
            "Dictionary of role groups to target. "
            "Valid structure: "
            '{"staff": ["volunteer", "moderator", ...], "candidate": ["screening", "league", ...]}'
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Overall broadcast delivery status.",
    )
    total_recipients = models.IntegerField(default=0)
    last_attempt = models.DateTimeField(null=True, blank=True)
    task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Celery task ID for async tracking.",
    )
    scheduled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Broadcast"
        verbose_name_plural = "Broadcasts"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        mediums = ", ".join(self.mediums)
        target_parts = []
        if self.target_roles.get("staff"):
            target_parts.append(f"Staff: {', '.join(self.target_roles['staff'])}")
        if self.target_roles.get("candidate"):
            target_parts.append(f"Candidate: {', '.join(self.target_roles['candidate'])}")
        target_roles = " | ".join(target_parts) if target_parts else "No targets"
        return f"{self.subject} [{mediums}] -> [{target_roles}] ({self.status})"

    def clean(self) -> None:
        """
        Validates the structure and contents of target_roles.

        Raises ValidationError if:
        - target_roles is not a dict.
        - Any keys other than 'staff' or 'candidate' are present.
        - Any role values are not valid choices for their respective model.
        """
        from django.core.exceptions import ValidationError

        if not isinstance(self.target_roles, dict):
            raise ValidationError("target_roles must be a dictionary.")

        valid_keys = {"staff", "candidate"}
        invalid_keys = set(self.target_roles.keys()) - valid_keys
        if invalid_keys:
            raise ValidationError(f"Invalid keys in target_roles: {invalid_keys}")

        if "staff" in self.target_roles:
            valid_staff_roles = {choice[0] for choice in Staff.Roles.choices}
            invalid = set(self.target_roles["staff"]) - valid_staff_roles
            if invalid:
                raise ValidationError(f"Invalid staff roles: {invalid}")

        if "candidate" in self.target_roles:
            valid_candidate_roles = {choice[0] for choice in Candidate.Roles.choices}
            invalid = set(self.target_roles["candidate"]) - valid_candidate_roles
            if invalid:
                raise ValidationError(f"Invalid candidate roles: {invalid}")


class BroadcastLog(models.Model):
    """
    Records the delivery outcome for a single medium-role combination within
    a Broadcast.

    For example, a broadcast targeting staff:volunteer via both Email and
    SMS will produce two BroadcastLog entries. This granularity allows
    partial retries and precise failure attribution.
    """

    class MediumStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    COMBINED_ROLE_CHOICES = list(Candidate.Roles.choices) + list(Staff.Roles.choices)

    id = models.AutoField(primary_key=True)
    broadcast = models.ForeignKey(
        Broadcast,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    medium = models.CharField(max_length=20, choices=Broadcast.Mediums.choices)
    target_role = models.CharField(max_length=20, choices=COMBINED_ROLE_CHOICES)
    role_type = models.CharField(
        max_length=10,
        default="candidate",
        choices=[("staff", "Staff"), ("candidate", "Candidate")],
        help_text="Whether this log entry targets a staff or candidate role.",
    )
    status = models.CharField(
        max_length=20,
        choices=MediumStatus.choices,
        default=MediumStatus.PENDING,
    )
    message = models.TextField(blank=True, help_text="Error or status message.")
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Broadcast Log"
        verbose_name_plural = "Broadcast Logs"
        ordering = ["-attempted_at"]

    def __str__(self) -> str:
        return (
            f"{self.broadcast.subject} "
            f"[{self.medium} -> {self.role_type}:{self.target_role}] "
            f"{self.status}"
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class Notification(models.Model):
    """
    A real-time, in-platform notification delivered to a specific user.

    Notifications are created by the notification service and pushed
    immediately to the recipient's WebSocket group (user__<id>) via
    Django Channels. They persist in the database to populate notification
    history on the dashboard.

    expires_at can be set to automatically suppress stale notifications
    in the UI. is_archived provides soft-removal without data loss.
    """

    class Type(models.TextChoices):
        ALERT = "alert", "Alert"
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    recipient = models.ForeignKey(
        "identity.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    subject = models.CharField(max_length=100)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.ALERT,
        db_index=True,
    )
    link = models.URLField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Notification for {self.recipient.email}: {self.subject}"


# ---------------------------------------------------------------------------
# System / Infrastructure
# ---------------------------------------------------------------------------
class BackupLog(models.Model):
    """
    Records the outcome of a scheduled database backup operation.

    Populated by the backup pipeline and surfaced to engineers via Slack
    alerts on failure. SUCCESS_AFTER_RETRY distinguishes recoveries from
    clean first-attempt successes for monitoring purposes.
    """

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

    def __str__(self) -> str:
        return f"BackupLog [{self.environment}] {self.timestamp}: {self.status}"