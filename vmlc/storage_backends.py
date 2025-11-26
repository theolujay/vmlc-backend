from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class PublicMediaStorage(S3Boto3Storage):
    """
    Storage for files that can be publicly accessible (like profile photos)
    These files get public URLs that don't expire
    """

    location = "media/public"
    default_acl = "public-read"
    file_overwrite = False

    def __init__(self, *args, **kwargs):
        kwargs.update(
            {
                "access_key": settings.AWS_ACCESS_KEY_ID,
                "secret_key": settings.AWS_SECRET_ACCESS_KEY,
                "bucket_name": settings.AWS_STORAGE_BUCKET_NAME,
                "region_name": settings.AWS_S3_REGION_NAME,
                "custom_domain": settings.AWS_S3_CUSTOM_DOMAIN,
            }
        )
        super().__init__(*args, **kwargs)


class PrivateMediaStorage(S3Boto3Storage):
    """
    Storage for sensitive files that need access control (ID cards, verification docs)
    These files generate signed URLs that expire
    """

    location = "media/private"
    default_acl = "private"
    file_overwrite = False
    querystring_auth = True  # Generate signed URLs
    querystring_expire = 3600  # URLs expire in 1 hour

    def __init__(self, *args, **kwargs):
        kwargs.update(
            {
                "access_key": settings.AWS_ACCESS_KEY_ID,
                "secret_key": settings.AWS_SECRET_ACCESS_KEY,
                "bucket_name": settings.AWS_STORAGE_BUCKET_NAME,
                "region_name": settings.AWS_S3_REGION_NAME,
                "custom_domain": False,  # Don't use custom domain for signed URLs
            }
        )
        super().__init__(*args, **kwargs)
