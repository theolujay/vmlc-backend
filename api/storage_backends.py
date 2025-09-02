from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
from typing import Any


class PublicMediaStorage(S3Boto3Storage):
    """
    Storage for files that can be publicly accessible (like profile photos)
    These files get public URLs that don't expire
    """

    location: str = "media/public"
    default_acl: str = "public-read"
    file_overwrite: bool = False
    custom_domain: bool = True  # Use your custom domain for better performance

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["custom_domain"] = settings.AWS_S3_CUSTOM_DOMAIN
        super().__init__(*args, **kwargs)


class PrivateMediaStorage(S3Boto3Storage):
    """
    Storage for sensitive files that need access control (ID cards, verification docs)
    These files generate signed URLs that expire
    """

    location: str = "media/private"
    default_acl: str = "private"
    file_overwrite: bool = False
    querystring_auth: bool = True  # Generate signed URLs
    querystring_expire: int = 3600  # URLs expire in 1 hour
    custom_domain: bool = False  # Don't use custom domain for signed URLs

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Ensure we don't use custom domain for private files
        kwargs["custom_domain"] = False
        super().__init__(*args, **kwargs)
