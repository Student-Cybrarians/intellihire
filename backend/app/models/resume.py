"""
app/models/resume.py
─────────────────────
Beanie document model for storing parsed resume data in MongoDB.
"""

from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import EmailStr, Field


class WorkExperience(Document):
    """Embedded: one job entry."""
    company: str = ""
    role: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[int] = None
    description: str = ""
    technologies: List[str] = []

    class Settings:
        # Not a top-level collection — used as embedded model
        is_root: bool = False


class Education(Document):
    """Embedded: one education entry."""
    institution: str = ""
    degree: str = ""
    field: str = ""
    year: Optional[str] = None
    gpa: Optional[str] = None

    class Settings:
        is_root: bool = False


class Project(Document):
    """Embedded: one project entry."""
    name: str = ""
    description: str = ""
    technologies: List[str] = []
    url: Optional[str] = None

    class Settings:
        is_root: bool = False


class ResumeDocument(Document):
    """
    Top-level MongoDB document for a parsed resume.
    Stored in the 'resumes' collection.
    """

    # ── Identity ─────────────────────────────────────────
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None

    # ── Content ───────────────────────────────────────────
    raw_text: str = ""                  # full extracted text (for debugging)
    skills: List[str] = []
    soft_skills: List[str] = []
    education: List[dict] = []          # list of Education dicts
    experience: List[dict] = []         # list of WorkExperience dicts
    projects: List[dict] = []           # list of Project dicts
    certifications: List[str] = []
    languages: List[str] = []
    summary: Optional[str] = None

    # ── Metadata ──────────────────────────────────────────
    original_filename: str = ""
    file_type: str = ""                 # pdf | docx
    word_count: int = 0
    char_count: int = 0
    section_flags: dict = {}            # which sections were detected
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "resumes"                # MongoDB collection name
        indexes = [
            [("email", 1)],
            [("uploaded_at", -1)],
        ]
