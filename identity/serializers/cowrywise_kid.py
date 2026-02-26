from rest_framework import serializers

from identity.models import CowrywiseKidProfile


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
        if "username" in validated_data:
            validated_data["username"] = validated_data["username"].lower()

        return CowrywiseKidProfile.objects.create(**validated_data)
