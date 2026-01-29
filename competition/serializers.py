from rest_framework import serializers

class PublishStandingsSerializer(serializers.Serializer):
    """
    Serializer for triggering the standings generation/publish process.
    """
    stage_exam_id = serializers.UUIDField(
        help_text="UUID of the StageExam to generate standings for."
    )
    publish_now = serializers.BooleanField(
        default=False,
        help_text="If True, immediately marks the generated standings as published."
    )
