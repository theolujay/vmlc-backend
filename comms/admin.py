from django.contrib import admin
from django.utils.html import format_html
from celery.result import AsyncResult

from comms.models import (
    Broadcast,
    BroadcastLog,
    Notification,
    BackupLog,
    PublicSupportRequest,
    HelpdeskThread,
    ThreadMessage,
)


@admin.register(PublicSupportRequest)
class PublicSupportRequestAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "type", "organization", "created_at"]
    list_filter = ["type", "created_at"]
    search_fields = ["full_name", "email", "organization", "message"]
    date_hierarchy = "created_at"


class ThreadMessageInline(admin.TabularInline):
    model = ThreadMessage
    extra = 0
    readonly_fields = ["created_at"]
    fields = ["sender", "sender_type", "text", "metadata", "created_at"]


@admin.register(HelpdeskThread)
class HelpdeskThreadAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "candidate",
        "assigned_staff",
        "status",
        "priority",
        "last_message_at",
        "created_at",
    ]
    list_filter = ["status", "priority", "created_at"]
    search_fields = [
        "candidate__email",
        "candidate__first_name",
        "candidate__last_name",
        "assigned_staff__user__email",
    ]
    inlines = [ThreadMessageInline]
    date_hierarchy = "created_at"
    autocomplete_fields = ["candidate", "assigned_staff"]


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "subject",
        "status",
        "created_by",
        "scheduled_at",
        "sent_at",
        "retry_count",
        "created_at",
    ]
    list_filter = ["status", "created_at", "mediums", "created_by", "retry_count"]
    search_fields = [
        "subject",
        "message",
        "created_by__email",
        "created_by__user__first_name",
    ]
    readonly_fields = ["task_result_display", "sent_at", "last_attempt"]
    autocomplete_fields = ["created_by"]
    list_select_related = ["created_by", "created_by__user"]
    date_hierarchy = "created_at"

    def task_status_display(self, obj):
        if not obj.task_id:
            return "No Task"

        task_result = AsyncResult(obj.task_id)

        color = {
            "SUCCESS": "green",
            "FAILURE": "red",
            "PENDING": "orange",
            "RETRY": "blue",
        }.get(task_result.status, "gray")

        return format_html(
            '<span style="color: {};">{}</span>', color, task_result.status
        )

    task_status_display.short_description = "Task Status"

    def task_result_display(self, obj):
        if not obj.task_id:
            return "No task ID"

        task_result = AsyncResult(obj.task_id)

        if task_result.successful() and task_result.result:
            summary = task_result.result
            return format_html(
                """
                <strong>Task Result Summary:</strong><br>
                Total Attempts: {}<br>
                Successful: {}<br>
                Success Rate: {:.1f}%<br>
                Completed: {}
                """,
                summary.get("total_attempts", "N/A"),
                summary.get("successful_attempts", "N/A"),
                (
                    summary.get("successful_attempts", 0)
                    / max(summary.get("total_attempts", 1), 1)
                    * 100
                ),
                summary.get("completed_at", "N/A"),
            )
        elif task_result.failed():
            return format_html(
                '<span style="color: red;">Task Failed: {}</span>',
                str(task_result.result)[:200],
            )
        else:
            return f"Task Status: {task_result.status}"

    task_result_display.short_description = "Task Result Details"


@admin.register(BroadcastLog)
class BroadcastLogAdmin(admin.ModelAdmin):
    list_display = [
        "broadcast",
        "medium",
        "target_role",
        "role_type",
        "status",
        "recipient_count",
        "sent_at",
        "attempted_at",
    ]
    list_filter = ["status", "medium", "role_type", "attempted_at", "sent_at"]
    search_fields = ["broadcast__subject", "message"]
    readonly_fields = ["attempted_at", "sent_at"]
    list_select_related = ["broadcast"]
    date_hierarchy = "attempted_at"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "recipient",
        "subject",
        "type",
        "is_read",
        "created_at",
    ]
    list_filter = ["type", "is_read", "created_at"]
    search_fields = ["recipient__email", "recipient__first_name", "subject", "message"]
    readonly_fields = ["created_at"]
    list_select_related = ["recipient"]
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_cache(obj)

    def delete_model(self, request, obj):
        self._invalidate_cache(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._invalidate_cache(obj)
        super().delete_queryset(request, queryset)

    def _invalidate_cache(self, obj):
        from vmlc.utils.cache import invalidate_candidate_cache

        if hasattr(obj.recipient, "candidate_profile"):
            invalidate_candidate_cache(
                obj.recipient.candidate_profile.id, obj.recipient.id
            )


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ["environment", "status", "timestamp", "backup_filename"]
    list_filter = ["environment", "status", "created_at"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
