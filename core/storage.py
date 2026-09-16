"""Secure file storage backends, UUID path generators, and image re-encoding helpers."""
import os
import uuid
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage


class PrivateFileSystemStorage(FileSystemStorage):
    """Storage backend for sensitive uploads stored in media/private/."""

    def __init__(self, **kwargs):
        kwargs.setdefault("location", os.path.join(settings.MEDIA_ROOT, "private"))
        kwargs.setdefault("base_url", None)
        super().__init__(**kwargs)


private_storage = PrivateFileSystemStorage()


def generate_secure_filename(instance, filename, prefix=""):
    """Generate a non-user-controlled UUID-based filename."""
    ext = os.path.splitext(filename)[1].lower()
    if not ext or len(ext) > 10:
        ext = ".bin"
    secure_name = f"{uuid.uuid4().hex}{ext}"
    if prefix:
        return os.path.join(prefix, secure_name)
    return secure_name


def secure_private_guest_id_path(instance, filename):
    return generate_secure_filename(instance, filename, prefix="guest_ids")


def secure_profile_pic_path(instance, filename):
    return generate_secure_filename(instance, filename, prefix="profile_pics")


def secure_category_image_path(instance, filename):
    return generate_secure_filename(instance, filename, prefix="category_images")


def secure_menu_item_image_path(instance, filename):
    return generate_secure_filename(instance, filename, prefix="menu_items")


def secure_room_image_path(instance, filename):
    return generate_secure_filename(instance, filename, prefix="rooms")


def reencode_image(uploaded_file):
    """Sanitize and re-encode an image using Pillow to strip EXIF and embedded data."""
    if not uploaded_file:
        return uploaded_file

    try:
        from PIL import Image
    except ImportError:
        return uploaded_file

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            fmt = img.format if img.format in ("JPEG", "PNG", "WEBP") else "JPEG"
            buf = BytesIO()
            # Convert RGBA to RGB for JPEG
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(buf, format=fmt, optimize=True)
            buf.seek(0)

            name = getattr(uploaded_file, "name", "upload.jpg")
            return ContentFile(buf.read(), name=name)
    except Exception:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        return uploaded_file
