"""
This package contains all the serializers for the API.
"""

from vmlc.v2.serializers.registration import RegistrationV2Serializer
from vmlc.v2.serializers.answer import (
    AutoSaveAnswerSerializer,
    AutoSaveAnswersBulkSerializer,
)


__all__ = [
    "RegistrationV2Serializer",
    "AutoSaveAnswerSerializer",
    "AutoSaveAnswersBulkSerializer",
]
