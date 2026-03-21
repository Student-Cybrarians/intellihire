"""
app/models/analysis.py
───────────────────────
Beanie document for storing ATS analysis results.
"""

from datetime import datetime
from typing import Dict, List, Optional

from beanie import Document
from pydantic import Field


class ScoreBreakdown(Document):
    """Embedded: individual score component."""
    component: str
    raw_score: float       # 0.0 – 1.0
    weighted_score: float  # raw_score × weight
    weight: float
    explanation: str

    class Settings:
        is_root: bool = False


class AnalysisDocument(Document):
    """
    Stores the full ATS analysis result for a resume ↔ JD pair.
    Collection: 'analyses'
    """

    resume_id: str                      # references ResumeDocument._id
    jd_id: Optional[str] = None        # references JobDescriptionDocument._id

    # ── Scores ────────────────────────────────────────────
    ats_score: float = 0.0             # final 0–100
    match_percentage: float = 0.0      # semantic similarity %
    score_breakdown: List[dict] = []   # list of ScoreBreakdown dicts

    # ── Gap Analysis ──────────────────────────────────────
    matched_keywords: List[str] = []
    missing_keywords: List[str] = []
    missing_skills: List[str] = []     # prioritised
    extra_skills: List[str] = []       # skills not in JD (still valuable)

    # ── LLM Output ────────────────────────────────────────
    improvement_suggestions: List[str] = []
    enhanced_bullets: List[dict] = []  # [{original, enhanced}]
    missing_sections: List[str] = []

    # ── Report paths ──────────────────────────────────────
    report_json_path: Optional[str] = None
    report_pdf_path: Optional[str] = None

    # ── Meta ──────────────────────────────────────────────
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    llm_model_used: str = ""

    class Settings:
        name = "analyses"
        indexes = [
            [("resume_id", 1)],
            [("analyzed_at", -1)],
        ]


class JobDescriptionDocument(Document):
    """
    Stores parsed job descriptions so they can be reused.
    Collection: 'job_descriptions'
    """

    title: str = ""
    company: Optional[str] = None
    raw_text: str = ""
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    keywords: List[str] = []
    experience_years: Optional[int] = None
    domain: Optional[str] = None       # e.g. "software engineering"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "job_descriptions"
