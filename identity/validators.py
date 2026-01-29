import os
from django.core.exceptions import ValidationError

def validate_verification_document(value):
    """Validate verification document"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported document format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Document size cannot exceed 5MB.")


def validate_profile_picture(value):
    """Validate profile picture file"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported image format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Image size cannot exceed 5MB.")


def validate_id_card_file(value):
    """Validate that the uploaded file is an image or PDF"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported file extension. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("File size cannot exceed 5MB.")


def validate_face_id(value):
    """Validate face ID file"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported image format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Image size cannot exceed 5MB.")


def validate_document_file(value):
    """Validate verification document file"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported document format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Document size cannot exceed 5MB.")
