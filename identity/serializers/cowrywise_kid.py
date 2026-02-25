


from rest_framework import serializers

from identity.models import CowrywiseKidProfile
from vmlc.utils.exceptions import ValidationError

class CowrywiseKidProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CowrywiseKidProfile
        fields = [
            "username",
            "candidate",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["candidate", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not hasattr(request.user, "candidate_profile"):
            return None

        candidate = request.user.candidate_profile
        username = validated_data.get("username").lower()
        cowrywise_kid, created = CowrywiseKidProfile.objects.get_or_create(
            candidate=candidate,
            username=username,
            defaults={
                "candidate": candidate,
                "username": username,
            }
        )
        return cowrywise_kid