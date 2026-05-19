import logging
import math
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from vmlc.models import ExamAccess, ExamHeartbeat, ViolationEvent
from vmlc.serializers.proctoring import (
    HEARTBEAT_INTERVAL_MINUTES,
    HEARTBEAT_INTERVAL_TOLERANCE_SECONDS,
)

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

RECENCY_WEIGHT_DECAY = 0.5

SUSPICION_THRESHOLDS = {
    "flagged": 0.7,
    "suspicious": 0.3,
}

BURST_DETECTION = {
    "min_violations": 3,
    "time_window_seconds": 10,
    "multiplier": 1.5,
}


class ProctoringService:
    @staticmethod
    def calculate_suspicion_score(summary):
        """
        Calculates a score between 0.0 and 1.0 based on the frequency of violations.
        Uses square root scaling for more balanced scoring across violation counts.
        """
        score = 0.0
        for event_type, count in summary.items():
            weight = SUSPICION_WEIGHTS.get(event_type, 0.05)
            if count > 0:
                score += weight * (1 + math.sqrt(count))

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

        heartbeat, _ = ExamHeartbeat.objects.get_or_create(
            sequence_number=payload.get("sequence_number"),
            client_uuid=client_uuid,
            defaults={
                "exam_access": exam_access,
                "period_start": payload.get("period_start"),
                "period_end": payload.get("period_end"),
                "summary": summary,
                "face_capture": face_capture,
                # Suspicion score will be updated by the task
                "suspicion_score": 0.0,
                "meta": payload.get("meta", {}),
            },
        )

        # Invalidate integrity audit cache
        from core.utils.cache import invalidate_integrity_audit_cache

        invalidate_integrity_audit_cache(exam_access.exam_id, exam_access.candidate_id)

        # Trigger the async task to process events and calculate score
        from vmlc.tasks import process_heartbeat_events_task

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

        # Trigger WebSocket update for Helpdesk Thread if it exists
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        from comms.models import HelpdeskThread
        from vmlc.serializers.proctoring import CandidateLiveStatusV2Serializer

        try:
            thread = HelpdeskThread.objects.get(candidate=access.candidate)
            channel_layer = get_channel_layer()
            status_data = CandidateLiveStatusV2Serializer(access).data

            async_to_sync(channel_layer.group_send)(
                f"helpdesk_thread_{str(thread.id)}",
                {"type": "helpdesk.thread.exam_telemetry", "data": status_data},
            )
        except HelpdeskThread.DoesNotExist:
            pass

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
        heartbeats = list(exam_access.heartbeats.all().order_by("sequence_number"))

        received_count = len(heartbeats)

        total_violations = sum(
            h.summary.get(k, 0) for h in heartbeats for k in h.summary
        )
        critical_count = ViolationEvent.objects.filter(
            heartbeat__exam_access=exam_access, is_critical=True
        ).count()

        integrity_details = ProctoringService._calculate_proctoring_integrity(
            heartbeats
        )

        burst_multiplier = 1.0
        if received_count > 0:
            burst_multiplier = ProctoringService._detect_burst_violations(exam_access)

        avg_suspicion = (
            sum(h.suspicion_score * burst_multiplier for h in heartbeats)
            / received_count
            if received_count > 0
            else 0.0
        )

        avg_suspicion = ProctoringService._apply_recency_weighting(
            heartbeats, avg_suspicion
        )

        avg_suspicion = ProctoringService._apply_duration_normalization(
            exam_access, heartbeats, avg_suspicion
        )

        avg_suspicion = min(1.0, avg_suspicion)

        auto_status = ProctoringService.determine_status(avg_suspicion, critical_count)
        if received_count == 0:
            auto_status = None

        return {
            "total_heartbeats": received_count,
            "total_violations": total_violations,
            "critical_violations": critical_count,
            "proctoring_integrity": round(integrity_details["score"], 2),
            "integrity_flags": integrity_details["flags"],
            "average_suspicion": round(avg_suspicion, 2),
            "auto_status": auto_status,
            "status": exam_access.proctoring_status,
            "is_manually_reviewed": exam_access.is_manually_reviewed,
        }

    @staticmethod
    def _detect_burst_violations(exam_access):
        """
        Detects if there are clusters of violations occurring in a short time window.
        Returns a multiplier to apply to the suspicion score.
        """

        events = ViolationEvent.objects.filter(
            heartbeat__exam_access=exam_access
        ).order_by("timestamp")

        if events.count() < BURST_DETECTION["min_violations"]:
            return 1.0

        events_list = list(events.values_list("timestamp", flat=True))
        max_multiplier = 1.0

        for i in range(len(events_list)):
            window_start = events_list[i]
            window_end = window_start + timedelta(
                seconds=BURST_DETECTION["time_window_seconds"]
            )

            count_in_window = sum(1 for ts in events_list[i:] if ts <= window_end)

            if count_in_window >= BURST_DETECTION["min_violations"]:
                max_multiplier = max(max_multiplier, BURST_DETECTION["multiplier"])

        return max_multiplier

    @staticmethod
    def _apply_recency_weighting(heartbeats, base_avg):
        """
        Applies exponential decay weighting so more recent heartbeats have higher weight.
        """
        if not heartbeats or len(heartbeats) <= 1:
            return base_avg

        n = len(heartbeats)
        weights = [RECENCY_WEIGHT_DECAY**i for i in range(n)]
        total_weight = sum(weights)

        weighted_sum = sum(
            h.suspicion_score * w for h, w in zip(reversed(heartbeats), weights)
        )

        return weighted_sum / total_weight

    @staticmethod
    def _apply_duration_normalization(exam_access, heartbeats, base_avg):
        """
        Normalizes suspicion score based on exam duration vs expected heartbeats.
        """
        if not exam_access.started_at or not heartbeats:
            return base_avg

        submitted_at = exam_access.submitted_at or timezone.now()
        duration = submitted_at - exam_access.started_at
        duration_minutes = duration.total_seconds() / 60

        expected_heartbeats = duration_minutes / HEARTBEAT_INTERVAL_MINUTES

        if expected_heartbeats <= 0:
            return base_avg

        coverage_ratio = len(heartbeats) / expected_heartbeats

        return base_avg * (1 + math.log1p(coverage_ratio))

    @staticmethod
    def _calculate_proctoring_integrity(heartbeats):
        """
        Calculate a more robust integrity score that accounts for:
        - Sequence gaps (missing heartbeats)
        - Time gaps (heartbeats with irregular intervals)
        - Coverage (how many expected heartbeats we got)
        """
        if hasattr(heartbeats, "order_by"):
            heartbeats_list = list(heartbeats.order_by("sequence_number"))
        else:
            heartbeats_list = sorted(heartbeats, key=lambda h: h.sequence_number)

        received_count = len(heartbeats_list)

        if received_count == 0:
            return {"score": 1.0, "flags": []}

        # Get sequence numbers
        sequences = [h.sequence_number for h in heartbeats_list]
        max_seq = max(sequences)

        # Count sequence gaps
        expected_sequences = set(range(1, max_seq + 1))
        actual_sequences = set(sequences)
        missing_sequences = expected_sequences - actual_sequences
        sequence_gap_count = len(missing_sequences)

        # Calculate time gaps (heartbeats with irregular intervals)
        time_gaps = []
        for i in range(1, len(heartbeats_list)):
            prev_hb = heartbeats_list[i - 1]
            curr_hb = heartbeats_list[i]

            # Calculate actual interval from period_end to period_start
            if prev_hb.period_end and curr_hb.period_start:
                interval = (curr_hb.period_start - prev_hb.period_end).total_seconds()
                expected_interval = HEARTBEAT_INTERVAL_MINUTES * 60
                tolerance = HEARTBEAT_INTERVAL_TOLERANCE_SECONDS

                # If gap exceeds expected + tolerance, it's a time gap
                if interval > expected_interval + tolerance:
                    time_gaps.append(
                        {
                            "from_seq": prev_hb.sequence_number,
                            "to_seq": curr_hb.sequence_number,
                            "gap_seconds": interval,
                        }
                    )

        time_gap_count = len(time_gaps)

        # Build flags for transparency
        flags = []
        if sequence_gap_count > 0:
            flags.append(
                {
                    "type": "sequence_gaps",
                    "count": sequence_gap_count,
                    "missing": sorted(list(missing_sequences)),
                    "severity": "high" if sequence_gap_count > 2 else "medium",
                }
            )

        if time_gap_count > 0:
            flags.append(
                {
                    "type": "time_gaps",
                    "count": time_gap_count,
                    "details": time_gaps,
                    "severity": "medium",
                }
            )

        # Calculate integrity score with multiple factors
        # Base score: received / max_expected (but penalize for gaps)
        base_score = received_count / max_seq if max_seq > 0 else 1.0

        # Penalize for sequence gaps (each gap loses 0.1 from score)
        gap_penalty = min(0.3, sequence_gap_count * 0.1)

        # Penalize for time gaps (each time gap loses 0.05 from score)
        time_penalty = min(0.2, time_gap_count * 0.05)

        # Final score bounded between 0 and 1
        final_score = max(0.0, min(1.0, base_score - gap_penalty - time_penalty))

        return {
            "score": final_score,
            "flags": flags,
        }

    @staticmethod
    def determine_status(avg_suspicion, critical_count):
        if critical_count > 0 or avg_suspicion >= SUSPICION_THRESHOLDS["flagged"]:
            return "flagged"
        if avg_suspicion >= SUSPICION_THRESHOLDS["suspicious"]:
            return "suspicious"
        return "clear"
