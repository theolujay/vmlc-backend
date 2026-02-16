from rest_framework import serializers
from django.core.cache import cache


from identity.models import (
    Candidate,
)

from .user import UserSerializer
from vmlc.services.candidate_records import CandidateRecordService


class MinimalCandidateSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing candidate info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "user",
            "school_name",
            "school_type",
            "current_class",
            "role",
            "verification_document",
        ]


class CandidateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing candidate info.
    """

    user = UserSerializer(read_only=True)
    status = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            "user",
            "school_name",
            "school_type",
            "current_class",
            "role",
            "status",
            "profile_type",
        ]

    def get_status(self, obj: Candidate):
        return obj.status

    def get_profile_type(self, obj):
        return "candidate"


class CandidateDetailSerializer(serializers.ModelSerializer):
    """
    Detailed candidate serializer including:
    - latest score
    - all results
    - total and average score
    """

    user: UserSerializer = UserSerializer(read_only=True)
    records: serializers.SerializerMethodField = serializers.SerializerMethodField(
        help_text="Contains a detailed breakdown of the candidate's performance and list of available exams."
    )
    # face_id = serializers.SerializerMethodField()
    # id_card = serializers.SerializerMethodField()
    verification_document = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    is_setup_complete = serializers.SerializerMethodField()

    class Meta:
        model: Candidate = Candidate
        fields = [
            "user",
            "profile_type",
            "school_name",
            "school_type",
            "current_class",
            "role",
            "is_active",
            "status",
            "verification_document",
            "created_at",
            "updated_at",
            "records",
            "is_setup_complete",
        ]
        read_only_fields = ["created_at", "updated_at", "user"]

    def get_is_setup_complete(self, obj):
        return obj.user.is_setup_complete

    def get_records(self, obj: Candidate):
        """
        Returns a dictionary containing candidate's records (performance and available exams).
        """
        cache_key = f"candidate_records_{obj.pk}"
        records = cache.get(cache_key)
        if records is None:
            records = CandidateRecordService.get_candidate_records(obj)
            # Cache for 24 hours.
            cache.set(cache_key, records, timeout=86400)
        return records

    def get_face_id(self, obj: Candidate):
        """
        Safely returns the face ID URL if it exists, otherwise returns None.
        This prevents errors when a candidate hasn't uploaded a face ID.
        """
        if obj.face_id and hasattr(obj.face_id, "url"):
            return obj.face_id.url
        return None

    def get_verification_document(self, obj: Candidate):
        """
        Safely returns the verification document URL if it exists, otherwise returns None.
        This prevents errors when a candidate hasn't uploaded a verification document.
        """
        if obj.verification_document and hasattr(obj.verification_document, "url"):
            return obj.verification_document.url
        return None

    def get_id_card(self, obj: Candidate):
        """
        Safely returns the ID card URL if it exists, otherwise returns None.
        This prevents errors when a candidate hasn't uploaded an ID card.
        """
        if obj.id_card and hasattr(obj.id_card, "url"):
            return obj.id_card.url
        return None

    def get_profile_type(self, obj: Candidate):
        return "candidate"

    def get_status(self, obj: Candidate):
        return obj.status
