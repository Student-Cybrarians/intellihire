"""
app/schemas/resume.py
──────────────────────
Pydantic v2 schemas used for API request/response validation.
These are separate from Beanie models — models = DB layer, schemas = API layer.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────
# Sub-schemas (nested)
# ─────────────────────────────────────────────────────────

class WorkExperienceSchema(BaseModel):
    company: str = ""
    role: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: str = ""
    technologies: List[str] = []


class EducationSchema(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    year: Optional[str] = None
    gpa: Optional[str] = None


class ProjectSchema(BaseModel):
    name: str = ""
    description: str = ""
    technologies: List[str] = []
    url: Optional[str] = None


# ─────────────────────────────────────────────────────────
# Upload / Parse responses
# ─────────────────────────────────────────────────────────

class UploadResumeResponse(BaseModel):
    """Returned immediately after /upload_resume"""
    resume_id: str
    message: str
    filename: str
    word_count: int
    sections_detected: List[str]
    parsed_data: "ParsedResumeSchema"


class ParsedResumeSchema(BaseModel):
    """Full structured data extracted from a resume."""
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = []
    soft_skills: List[str] = []
    education: List[EducationSchema] = []
    experience: List[WorkExperienceSchema] = []
    projects: List[ProjectSchema] = []
    certifications: List[str] = []


# ─────────────────────────────────────────────────────────
# Analysis request / response
# ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """POST /analyze body"""
    resume_id: str = Field(..., description="ID returned from /upload_resume")
    job_description: str = Field(
        ...,
        min_length=50,
        description="Full job description text (minimum 50 characters)",
    )
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    enhance_bullets: bool = Field(
        default=True,
        description="Whether to use LLM to improve bullet points (adds ~2s)",
    )

    @field_validator("job_description")
    @classmethod
    def jd_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Job description cannot be empty")
        return v.strip()


class ScoreBreakdownSchema(BaseModel):
    component: str
    raw_score: float          # 0.0 – 1.0
    weighted_score: float     # raw_score × weight
    weight: float
    explanation: str


class AnalyzeResponse(BaseModel):
    """Returned from POST /analyze"""
    analysis_id: str
    resume_id: str

    # Core scores
    ats_score: float = Field(..., ge=0, le=100, description="ATS score 0–100")
    match_percentage: float = Field(..., ge=0, le=100)
    score_breakdown: List[ScoreBreakdownSchema]

    # Gap analysis
    matched_keywords: List[str]
    missing_keywords: List[str]
    missing_skills: List[str]          # ordered by priority
    extra_skills: List[str]

    # LLM suggestions
    improvement_suggestions: List[str]
    enhanced_bullets: List[Dict]       # [{original, enhanced}]
    missing_sections: List[str]

    # Report
    report_available: bool
    analyzed_at: datetime


# ─────────────────────────────────────────────────────────
# Resume generation
# ─────────────────────────────────────────────────────────

class GenerateResumeRequest(BaseModel):
    """POST /generate_resume body"""
    resume_id: Optional[str] = Field(
        None,
        description="If provided, uses existing parsed data as base",
    )

    # Manual overrides / new data
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[WorkExperienceSchema]] = None
    education: Optional[List[EducationSchema]] = None
    projects: Optional[List[ProjectSchema]] = None
    certifications: Optional[List[str]] = None

    # Options
    template: str = Field(default="modern", description="modern | minimal | classic")
    include_photo: bool = False
    target_job_title: Optional[str] = None
    analysis_id: Optional[str] = Field(
        None,
        description="If provided, uses LLM suggestions from analysis to enhance resume",
    )


class GenerateResumeResponse(BaseModel):
    """Returned from POST /generate_resume"""
    resume_id: str
    html_content: str          # ATS-friendly HTML
    pdf_path: str              # downloadable PDF path
    download_url: str
    template_used: str
    generated_at: datetime
