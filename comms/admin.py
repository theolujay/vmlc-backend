from django.contrib import admin
from django.utils.html import format_html
from celery.result import AsyncResult

from comms.models import (
    Broadcast,
    BroadcastLog,
    Notification,
    BackupLog,
)


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "subject",
        "status",
        "created_by",
        "created_at",
        "task_status_display",
    ]
    list_filter = ["status", "created_at", "mediums", "created_by"]
    readonly_fields = ["task_result_display"]
    autocomplete_fields = ["created_by"]

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
        "attempted_at",
    ]
    list_filter = ["status", "medium", "role_type", "attempted_at"]
    search_fields = ["broadcast__subject", "message"]
    readonly_fields = ["attempted_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "subject", "read", "created_at"]
    list_filter = ["read", "created_at"]
    search_fields = ["recipient__email", "recipient__first_name", "subject", "message"]
    readonly_fields = ["created_at"]


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ["environment", "status", "timestamp", "backup_filename"]
    list_filter = ["environment", "status", "created_at"]
    readonly_fields = ["created_at"]