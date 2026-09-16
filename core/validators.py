"""File upload validation routines enforcing size limits and binary magic signatures."""
import os
from django.core.exceptions import ValidationError

ALLOWED_MAGIC_SIGNATURES = {
    "jpeg": [b"\xFF\xD8\xFF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "pdf": [b"%PDF-"],
    "webp": [b"RIFF"],  # Checked in conjunction with WEBP string
}


def validate_file_signature(file):
    """Inspect binary header bytes to verify MIME type magic signature."""
    if not file:
        return

    # Extract initial chunk for header inspection
    pos = file.tell() if hasattr(file, "tell") else 0
    header = file.read(512)
    if hasattr(file, "seek"):
        file.seek(pos)

    if not header:
        raise ValidationError("Uploaded file is empty.")

    is_valid = False
    # Check JPEG
    if header.startswith(b"\xFF\xD8\xFF"):
        is_valid = True
    # Check PNG
    elif header.startswith(b"\x89PNG\r\n\x1a\n"):
        is_valid = True
    # Check PDF
    elif header.startswith(b"%PDF-"):
        is_valid = True
    # Check WEBP
    elif header.startswith(b"RIFF") and b"WEBP" in header[:16]:
        is_valid = True

    if not is_valid:
        raise ValidationError("Uploaded file binary signature is invalid or unrecognized.")


def validate_upload_size(file):
    """Enforce 5 MB maximum upload file size limit."""
    if not file:
        return
    max_bytes = 5 * 1024 * 1024
    if getattr(file, "size", 0) > max_bytes:
        raise ValidationError("Uploaded file exceeds maximum allowed size of 5 MB.")
