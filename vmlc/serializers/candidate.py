from rest_framework import serializers


from ..models import (
    Candidate,
)

from .user import UserSerializer, MinimalUserSerializer


class MinimalCandidateSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing candidate info.
    """

    user = MinimalUserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = ["user", "school", "role"]


class CandidateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing candidate info.
    """

    user = MinimalUserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "user",
            "school",
            "role",
            "is_verified",
        ]


class CandidateDetailSerializer(serializers.ModelSerializer):
    """
    Detailed candidate serializer including:
    - latest score
    - all scores
    - total and average score
    """

    user: UserSerializer = UserSerializer(read_only=True)
    scores: serializers.SerializerMethodField = serializers.SerializerMethodField(
        help_text="Detailed score breakdown for the candidate."
    )
    face_id = serializers.SerializerMethodField()
    id_card = serializers.SerializerMethodField()
    verification_document = serializers.SerializerMethodField()

    class Meta:
        model: Candidate = Candidate
        fields = [
            "user",
            "school",
            "face_id",
            "role",
            "is_active",
            "is_verified",
            "id_card",
            "verification_document",
            "date_created",
            "date_updated",
            "scores",
        ]
        read_only_fields = ["date_created", "date_updated", "user"]

    def get_scores(self, obj: Candidate):
        """
        Efficiently returns a dictionary of scores by leveraging the
        annotated and prefetched data from the model's `get_score_dict` method.
        """
        return obj.get_score_dict()
    
    def get_face_id(self, obj: Candidate):
        """
        Safely returns the face ID URL if it exists, otherwise returns None.
        This prevents errors when a candidate hasn't uploaded a face ID.
        """
        if obj.face_id and hasattr(obj.face_id, 'url'):
            return obj.face_id.url
        return None
    def get_verification_document(self, obj: Candidate):
        """
        Safely returns the verification document URL if it exists, otherwise returns None.
        This prevents errors when a candidate hasn't uploaded a verification document.
        """
        if obj.verification_document and hasattr(obj.verification_document, 'url'):
            return obj.verification_document.url
        return None
    def get_id_card(self, obj: Candidate):
        """
        Safely returns the ID card URL if it exists, otherwise returns None.
        This prevents errors when a candidate hasn't uploaded an ID card.
        """
        if obj.id_card and hasattr(obj.id_card, 'url'):
            return obj.id_card.url
        return None


