
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    User,
)


class UserSerializer(serializers.ModelSerializer):
    """
    Basic serializer for the Django User model.
    """

    # username = serializers.CharField(
    #     max_length=14, validators=[UniqueValidator(queryset=User.objects.all())]
    # )
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )


    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined")
