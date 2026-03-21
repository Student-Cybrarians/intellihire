"""
app/utils/file_utils.py
────────────────────────
File validation and handling utilities.
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Tuple

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError

# MIME types that are acceptable for each extension
ALLOWED_MIME_TYPES = {
    "pdf":  ["application/pdf", "application/x-pdf"],
    "docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/zip",          # DOCX is a ZIP archive
    ],
}


def validate_upload(filename: str, file_bytes: bytes) -> Tuple[str, str]:
    """
    Validate uploaded file: extension, size, and basic MIME check.

    Returns:
        (extension, sha256_hash) on success

    Raises:
        UnsupportedFileTypeError
        FileTooLargeError
    """
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(ext)

    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise FileTooLargeError(size_mb, settings.MAX_UPLOAD_SIZE_MB)

    # Magic byte check for PDF
    if ext == "pdf" and not file_bytes.startswith(b"%PDF"):
        raise UnsupportedFileTypeError("pdf (invalid magic bytes — not a real PDF)")

    # Magic byte check for DOCX (PK zip header)
    if ext == "docx" and not file_bytes[:2] == b"PK":
        raise UnsupportedFileTypeError("docx (invalid magic bytes — not a real DOCX)")

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    return ext, sha256


def human_size(num_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
