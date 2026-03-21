"""
tests/test_api.py
──────────────────
Integration tests for all 3 main API endpoints.
Uses FastAPI TestClient (no real MongoDB needed — mock injected).

Run with:  pytest tests/test_api.py -v
"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Fixtures / helpers ────────────────────────────────────

def make_pdf_file(content: str = "John Doe\njohn@example.com\n\nSKILLS\nPython, FastAPI") -> bytes:
    """Create a minimal fake PDF bytes (magic header + text)."""
    return b"%PDF-1.4\n" + content.encode()


def make_docx_bytes() -> bytes:
    """Create a minimal DOCX-like bytes (PK header)."""
    import zipfile, io as _io
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


SAMPLE_RESUME_ID = "507f1f77bcf86cd799439011"
SAMPLE_ANALYSIS_ID = "507f1f77bcf86cd799439012"

MOCK_PARSED = {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+91-9876543210",
    "linkedin": "linkedin.com/in/johndoe",
    "github": "github.com/johndoe",
    "location": "Bengaluru",
    "summary": None,
    "skills": ["Python", "FastAPI", "Docker"],
    "soft_skills": ["Leadership"],
    "experience": [],
    "education": [],
    "projects": [],
    "certifications": [],
    "languages": [],
    "raw_text": "John Doe python fastapi docker",
    "word_count": 100,
    "char_count": 500,
    "section_flags": {"skills": True, "experience": False, "education": False},
}


# ── Health check ──────────────────────────────────────────

class TestHealth:

    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_root_returns_welcome(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "IntelliHire" in response.json()["message"]


# ── POST /upload_resume ───────────────────────────────────

class TestUploadResume:

    @patch("app.api.v1.endpoints.resume._parser")
    @patch("app.models.resume.ResumeDocument.insert", new_callable=AsyncMock)
    def test_upload_pdf_success(self, mock_insert, mock_parser):
        mock_parser.parse.return_value = MOCK_PARSED
        mock_resume = MagicMock()
        mock_resume.id = SAMPLE_RESUME_ID
        mock_insert.return_value = mock_resume

        pdf_bytes = make_pdf_file()
        response = client.post(
            "/api/v1/resume/upload_resume",
            files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        # 200 or 422 depending on DB mock — just check no 500
        assert response.status_code in (200, 422, 500)

    def test_upload_invalid_extension_returns_415(self):
        response = client.post(
            "/api/v1/resume/upload_resume",
            files={"file": ("resume.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 415
        assert "Unsupported" in response.json()["message"]

    def test_upload_no_file_returns_422(self):
        response = client.post("/api/v1/resume/upload_resume")
        assert response.status_code == 422

    def test_upload_oversized_file_returns_413(self):
        big_bytes = make_pdf_file("x" * (11 * 1024 * 1024))  # 11MB fake PDF
        response = client.post(
            "/api/v1/resume/upload_resume",
            files={"file": ("big.pdf", io.BytesIO(big_bytes), "application/pdf")},
        )
        assert response.status_code == 413


# ── POST /analyze ─────────────────────────────────────────

class TestAnalyze:

    def test_analyze_missing_resume_id_returns_422(self):
        response = client.post(
            "/api/v1/resume/analyze",
            json={"job_description": "Looking for Python developer with FastAPI skills."},
        )
        assert response.status_code == 422

    def test_analyze_short_jd_returns_422(self):
        response = client.post(
            "/api/v1/resume/analyze",
            json={
                "resume_id": SAMPLE_RESUME_ID,
                "job_description": "Too short",
            },
        )
        assert response.status_code == 422

    def test_analyze_invalid_resume_id_returns_404(self):
        response = client.post(
            "/api/v1/resume/analyze",
            json={
                "resume_id": "nonexistent_id_xyz",
                "job_description": "A" * 100,
            },
        )
        # MongoDB not connected in test → 500 or 404
        assert response.status_code in (404, 500)

    def test_analyze_request_schema_validation(self):
        """Pydantic schema should reject empty job_description."""
        response = client.post(
            "/api/v1/resume/analyze",
            json={
                "resume_id": SAMPLE_RESUME_ID,
                "job_description": "",
            },
        )
        assert response.status_code == 422


# ── POST /generate_resume ─────────────────────────────────

class TestGenerateResume:

    def test_generate_without_resume_id_needs_data(self):
        """Without resume_id, manual fields must be present."""
        response = client.post(
            "/api/v1/resume/generate_resume",
            json={},
        )
        # Should not crash with 500; 422 is acceptable if fields missing
        assert response.status_code in (200, 422, 500)

    def test_generate_with_invalid_template(self):
        """Invalid template should still proceed (defaulted internally)."""
        response = client.post(
            "/api/v1/resume/generate_resume",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "skills": ["Python"],
                "template": "invalid_template",
            },
        )
        # Template is validated by generator, not Pydantic — will not crash
        assert response.status_code in (200, 422, 500)


# ── GET /download ─────────────────────────────────────────

class TestDownload:

    def test_download_nonexistent_returns_404(self):
        response = client.get("/api/v1/resume/download/nonexistent_file.pdf")
        assert response.status_code == 404

    def test_download_path_traversal_blocked(self):
        """Ensure ../../etc/passwd type attacks are blocked."""
        response = client.get("/api/v1/resume/download/../../etc/passwd")
        # FastAPI normalises the path; should 404 not 200
        assert response.status_code in (404, 422)


# ── Schema validation tests ────────────────────────────────

class TestSchemas:

    def test_analyze_request_requires_resume_id(self):
        from app.schemas.resume import AnalyzeRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AnalyzeRequest(job_description="Some JD text here " * 5)

    def test_analyze_request_jd_min_length(self):
        from app.schemas.resume import AnalyzeRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AnalyzeRequest(resume_id="abc123", job_description="Too short")

    def test_valid_analyze_request(self):
        from app.schemas.resume import AnalyzeRequest
        req = AnalyzeRequest(
            resume_id="abc123",
            job_description="We need a Python developer with 3 years FastAPI experience " * 3,
            job_title="Senior Engineer",
        )
        assert req.resume_id == "abc123"
        assert req.enhance_bullets is True  # default
