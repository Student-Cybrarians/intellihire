"""
app/core/exceptions.py
───────────────────────
Custom exception hierarchy for IntelliHire.
Each exception maps to an HTTP status code for consistent API responses.
"""

from fastapi import HTTPException


class IntelliHireException(Exception):
    """Base exception for all IntelliHire errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ResumeParseError(IntelliHireException):
    """Raised when resume cannot be parsed (corrupt file, unsupported format)."""
    def __init__(self, detail: str = "Failed to parse resume"):
        super().__init__(message=detail, status_code=422)


class UnsupportedFileTypeError(IntelliHireException):
    """Raised when an unsupported file extension is uploaded."""
    def __init__(self, ext: str):
        super().__init__(
            message=f"Unsupported file type: '{ext}'. Allowed: PDF, DOCX",
            status_code=415,
        )


class FileTooLargeError(IntelliHireException):
    """Raised when uploaded file exceeds MAX_UPLOAD_SIZE_MB."""
    def __init__(self, size_mb: float, limit_mb: int):
        super().__init__(
            message=f"File size {size_mb:.1f}MB exceeds limit of {limit_mb}MB",
            status_code=413,
        )


class LLMError(IntelliHireException):
    """Raised when LLM API call fails after retries."""
    def __init__(self, detail: str = "LLM service unavailable"):
        super().__init__(message=detail, status_code=503)


class DocumentNotFoundError(IntelliHireException):
    """Raised when a MongoDB document is not found."""
    def __init__(self, doc_id: str):
        super().__init__(
            message=f"Document '{doc_id}' not found",
            status_code=404,
        )


class EmptyResumeError(IntelliHireException):
    """Raised when parsed resume has no extractable content."""
    def __init__(self):
        super().__init__(
            message="Resume appears to be empty or image-only. Please provide a text-based resume.",
            status_code=422,
        )
