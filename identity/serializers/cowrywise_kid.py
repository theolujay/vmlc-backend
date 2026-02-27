from rest_framework import serializers

from identity.models import CowrywiseKidProfile


class CowrywiseKidProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the CowrywiseKidProfile model.
    """

    class Meta:
        model = CowrywiseKidProfile
        fields = ["username"]
        read_only_fields = ["candidate", "created_at"]
