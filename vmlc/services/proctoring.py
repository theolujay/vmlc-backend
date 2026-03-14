import logging
from django.db import transaction
from vmlc.models import ExamHeartbeat, ViolationEvent, ExamAccess

logger = logging.getLogger(__name__)

SUSPICION_WEIGHTS = {
    "TAB_SWITCH": 0.3,
    "MULTI_FACE": 0.5,
    "FULLSCREEN_EXIT": 0.1,
    "NO_FACE": 0.2,
    "DEVTOOLS_OPEN": 0.4,
    "SCREENSHOT": 0.1,
}

CRITICAL_EVENTS = ["MULTI_FACE", "DEVTOOLS_OPEN"]


class ProctoringService:
    @staticmethod
    def calculate_suspicion_score(summary):
        """
        Calculates a score between 0.0 and 1.0 based on the frequency of violations.
        """
        score = 0.0
        for event_type, count in summary.items():
            weight = SUSPICION_WEIGHTS.get(event_type, 0.05)
            # Logarithmic scaling for high counts to keep score within reasonable bounds
            import math

            if count > 0:
                score += weight * (1 + math.log10(count))

        return min(1.0, score)

    @staticmethod
    @transaction.atomic
    def process_heartbeat(exam_access, payload, face_capture=None):
        """
        Processes a heartbeat payload, saves models, and updates suspicion scores.
        """
        client_uuid = payload.get("client_uuid")

        # Idempotency check
        existing = ExamHeartbeat.objects.filter(client_uuid=client_uuid).first()
        if existing:
            logger.info(f"Duplicate heartbeat received: {client_uuid}")
            return existing

        summary = payload.get("summary", {})

        # We create the heartbeat object immediately to save the face_capture
        # but calculation and events will be handled by a task.
        heartbeat = ExamHeartbeat.objects.create(
            exam_access=exam_access,
            sequence_number=payload.get("sequence_number"),
            client_uuid=client_uuid,
            period_start=payload.get("period_start"),
            period_end=payload.get("period_end"),
            summary=summary,
            face_capture=face_capture,
            # Suspicion score will be updated by the task
            suspicion_score=0.0,
            meta=payload.get("meta", {}),
        )

        # Invalidate integrity audit cache
        from vmlc.v2.utils import invalidate_integrity_audit_cache

        invalidate_integrity_audit_cache(exam_access.exam_id, exam_access.candidate_id)

        # Trigger the async task to process events and calculate score
        from vmlc.v2.tasks import process_heartbeat_events_task

        # We pass only the data needed. events_data is a list of dicts.
        events_data = payload.get("events", [])

        # Use on_commit to ensure the heartbeat is in DB before task runs
        transaction.on_commit(
            lambda: process_heartbeat_events_task.delay(str(heartbeat.id), events_data)
        )

        return heartbeat

    @staticmethod
    @transaction.atomic
    def process_events_and_score(heartbeat_id, events_data):
        """
        Background task to create events and update the suspicion score.
        """
        try:
            heartbeat = ExamHeartbeat.objects.get(pk=heartbeat_id)
        except ExamHeartbeat.DoesNotExist:
            logger.error(f"Heartbeat {heartbeat_id} not found for event processing.")
            return

        # 1. Create ViolationEvents
        events_to_create = []
        for event in events_data:
            event_type = event.get("type")
            events_to_create.append(
                ViolationEvent(
                    heartbeat=heartbeat,
                    event_type=event_type,
                    timestamp=event.get("timestamp"),
                    is_critical=event_type in CRITICAL_EVENTS,
                    metadata=event.get("metadata", {}),
                )
            )

        if events_to_create:
            ViolationEvent.objects.bulk_create(events_to_create)

        # 2. Calculate and update suspicion score
        suspicion_score = ProctoringService.calculate_suspicion_score(heartbeat.summary)
        heartbeat.suspicion_score = suspicion_score
        heartbeat.save(update_fields=["suspicion_score"])

        # 3. Update the parent ExamAccess with the latest automated status
        # ONLY if it hasn't been manually reviewed by an admin yet.
        access = heartbeat.exam_access
        summary = ProctoringService.get_proctoring_summary(access)

        # Update RankingSnapshotEntry if it exists and is for the current exam
        from competition.models import RankingSnapshotEntry

        ranking_entry_qs = RankingSnapshotEntry.objects.filter(
            ranking_snapshot__exam=access.exam,
            candidate=access.candidate,
            ranking_snapshot__is_active=True,
        )

        # We always update violation_score if a ranking exists
        ranking_entry_qs.update(violation_score=summary["average_suspicion"])

        if not access.is_manually_reviewed:
            new_status = summary["auto_status"]
            access.proctoring_status = new_status
            access.save(update_fields=["proctoring_status"])

            # Also update status in ranking if not manually reviewed
            ranking_entry_qs.update(proctoring_status=new_status)

        return heartbeat

    @staticmethod
    @transaction.atomic
    def update_proctoring_status(exam_id, candidate_id, new_status):
        """
        Manually updates the proctoring status for an attempt.
        Updates both ExamAccess and the relevant RankingSnapshotEntry.
        Sets the is_manually_reviewed flag to True.
        """
        access = ExamAccess.objects.get(exam_id=exam_id, candidate_id=candidate_id)
        access.proctoring_status = new_status
        access.is_manually_reviewed = True
        access.save(update_fields=["proctoring_status", "is_manually_reviewed"])

        # Update ranking snapshot entry if it exists
        from competition.models import RankingSnapshotEntry

        RankingSnapshotEntry.objects.filter(
            ranking_snapshot__exam_id=exam_id, candidate_id=candidate_id
        ).update(proctoring_status=new_status)

        return access

    @staticmethod
    def get_proctoring_summary(exam_access):
        """
        Returns a high-level summary of proctoring data for an attempt.
        """
        heartbeats = exam_access.heartbeats.all()

        # If no heartbeats, we still return the manual status if it's not 'clear'
        # or just return basic info.
        received_count = heartbeats.count()

        total_violations = sum(
            h.summary.get(k, 0) for h in heartbeats for k in h.summary
        )
        critical_count = ViolationEvent.objects.filter(
            heartbeat__exam_access=exam_access, is_critical=True
        ).count()

        # Simple integrity check: max sequence vs count
        max_seq = 0
        if received_count > 0:
            max_seq = heartbeats.order_by("-sequence_number").first().sequence_number

        integrity_score = received_count / max_seq if max_seq > 0 else 1.0
        avg_suspicion = (
            sum(h.suspicion_score for h in heartbeats) / received_count
            if received_count > 0
            else 0.0
        )

        # Automated status vs manual status
        auto_status = ProctoringService.determine_status(avg_suspicion, critical_count)
        if received_count == 0:
            auto_status = None

        return {
            "total_heartbeats": received_count,
            "total_violations": total_violations,
            "critical_violations": critical_count,
            "integrity_score": round(integrity_score, 2),
            "average_suspicion": round(avg_suspicion, 2),
            "auto_status": auto_status,
            "status": exam_access.proctoring_status,
            "is_manually_reviewed": exam_access.is_manually_reviewed,
        }

    @staticmethod
    def determine_status(avg_suspicion, critical_count):
        if critical_count > 0 or avg_suspicion > 0.7:
            return "flagged"
        if avg_suspicion > 0.3:
            return "suspicious"
        return "clear"
