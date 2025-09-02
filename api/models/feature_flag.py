from django.db import models


class FeatureFlag(models.Model):
    key: models.CharField = models.CharField(max_length=50, unique=True)
    value: models.BooleanField = models.BooleanField(default=True)

    @classmethod
    def get_bool(cls, key: str, default: bool = True) -> bool:
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    def __str__(self) -> str:
        return f"{self.key}: {'Enabled' if self.value else 'Disabled'}"
