"""
app/api/v1/endpoints/resume.py
───────────────────────────────
All resume-related API endpoints for Module 1.

Routes:
  POST /upload_resume      — Upload + parse resume file
  POST /analyze            — Run ATS analysis vs JD
  POST /generate_resume    — Generate ATS-friendly resume
  GET  /resume/{id}        — Retrieve parsed resume
  GET  /analysis/{id}      — Retrieve analysis result
  GET  /download/{filename} — Download generated file
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    EmptyResumeError,
    FileTooLargeError,
    IntelliHireException,
    ResumeParseError,
    UnsupportedFileTypeError,
)
from app.generators.resume_generator import ResumeGenerator
from app.models.analysis import AnalysisDocument
from app.models.resume import ResumeDocument
from app.parsers.resume_parser import ResumeParser
from app.schemas.resume import (
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateResumeRequest,
    GenerateResumeResponse,
    UploadResumeResponse,
)
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/resume", tags=["Module 1 — ATS Resume"])
logger = logging.getLogger(__name__)

# Singleton services (created once, reused per request)
_parser   = ResumeParser()
_analyzer = AnalysisService()
_gen      = ResumeGenerator()


# ─────────────────────────────────────────────────────────
# POST /upload_resume
# ─────────────────────────────────────────────────────────

@router.post(
    "/upload_resume",
    response_model=UploadResumeResponse,
    summary="Upload and parse a resume (PDF or DOCX)",
    responses={
        200: {"description": "Resume parsed successfully"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported file type"},
        422: {"description": "Could not parse resume (empty or corrupted)"},
    },
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> UploadResumeResponse:
    """
    Upload a resume file and extract structured data.

    - Validates file type and size
    - Parses PDF (PyMuPDF) or DOCX (python-docx)
    - Extracts: name, email, phone, skills, experience, education, projects
    - Persists to MongoDB and returns resume_id for downstream calls
    """
    # ── Validation ──────────────────────────────────────
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(ext)

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise FileTooLargeError(size_mb, settings.MAX_UPLOAD_SIZE_MB)

    # ── Parse ────────────────────────────────────────────
    try:
        parsed = _parser.parse(file_bytes=file_bytes, file_type=ext)
    except (ResumeParseError, EmptyResumeError, UnsupportedFileTypeError):
        raise  # re-raise as-is, handled by exception handler
    except Exception as e:
        logger.exception(f"Unexpected parse error for {file.filename}: {e}")
        raise ResumeParseError(f"Failed to parse {file.filename}: {str(e)}")

    # ── Save to disk (for audit trail) ──────────────────
    saved_path = settings.UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    async with aiofiles.open(saved_path, "wb") as f_out:
        await f_out.write(file_bytes)

    # ── Persist to MongoDB ───────────────────────────────
    resume_doc = ResumeDocument(
        **{k: v for k, v in parsed.items() if k in ResumeDocument.model_fields},
        original_filename=file.filename,
        file_type=ext,
    )
    await resume_doc.insert()
    resume_id = str(resume_doc.id)

    logger.info(f"Resume uploaded: {resume_id} | {file.filename} | {parsed['word_count']} words")

    # ── Build response ───────────────────────────────────
    from app.schemas.resume import ParsedResumeSchema
    return UploadResumeResponse(
        resume_id=resume_id,
        message="Resume parsed successfully",
        filename=file.filename,
        word_count=parsed["word_count"],
        sections_detected=[k for k, v in parsed.get("section_flags", {}).items() if v],
        parsed_data=ParsedResumeSchema(**parsed),
    )


# ─────────────────────────────────────────────────────────
# POST /analyze
# ─────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Run ATS analysis: resume vs job description",
    responses={
        200: {"description": "Analysis complete"},
        404: {"description": "Resume not found"},
        503: {"description": "LLM service unavailable"},
    },
)
async def analyze_resume(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyse a previously uploaded resume against a job description.

    Computes:
    - **ATS Score** (0–100) using 6 weighted components
    - **Match %** via semantic embedding similarity
    - **Missing keywords** and **skills gap**
    - **LLM-powered improvement suggestions**
    - **Enhanced bullet points** (if enhance_bullets=true)

    Persists full analysis to MongoDB and generates PDF + JSON reports.
    """
    return await _analyzer.analyze(request)


# ─────────────────────────────────────────────────────────
# POST /generate_resume
# ─────────────────────────────────────────────────────────

@router.post(
    "/generate_resume",
    response_model=GenerateResumeResponse,
    summary="Generate an ATS-optimised resume as HTML + PDF",
)
async def generate_resume(request: GenerateResumeRequest) -> GenerateResumeResponse:
    """
    Generate a clean, ATS-friendly resume.

    - If resume_id is provided: loads parsed data from MongoDB as base
    - Manual fields override stored data
    - If analysis_id is provided: uses LLM-enhanced bullets
    - Returns HTML (inline) + downloadable PDF link
    """
    user_data: dict = {}

    # Load base from existing parsed resume
    if request.resume_id:
        resume_doc = await ResumeDocument.get(request.resume_id)
        if not resume_doc:
            raise DocumentNotFoundError(request.resume_id)
        user_data = resume_doc.dict()

    # Apply manual overrides
    override_fields = [
        "name", "email", "phone", "linkedin", "github", "summary",
        "skills", "experience", "education", "projects", "certifications",
    ]
    for field in override_fields:
        val = getattr(request, field, None)
        if val is not None:
            user_data[field] = val if not hasattr(val, "dict") else [
                v.dict() for v in val
            ] if isinstance(val, list) else val.dict()

    # Apply LLM-enhanced bullets from analysis
    if request.analysis_id:
        analysis = await AnalysisDocument.get(request.analysis_id)
        if analysis and analysis.enhanced_bullets:
            # Map enhanced bullets back to experience entries
            bullet_map: dict = {}
            for b in analysis.enhanced_bullets:
                orig = b.get("original", "")
                enh  = b.get("enhanced", "")
                bullet_map[orig] = enh

            for exp in user_data.get("experience", []):
                bullets = [
                    l.strip().lstrip("•-–*").strip()
                    for l in exp.get("description", "").split("\n")
                    if l.strip()
                ]
                exp["enhanced_bullets"] = [
                    {"original": b, "enhanced": bullet_map.get(b, b)}
                    for b in bullets
                ]

    # Run LLM content enhancement
    from app.services.llm_service import LLMService
    llm = LLMService()
    user_data = await llm.generate_resume_content(
        user_data, target_role=request.target_job_title
    )

    # Generate resume
    result = await _gen.generate(user_data, template=request.template)

    # Persist updated resume
    new_resume = ResumeDocument(
        **{k: v for k, v in user_data.items() if k in ResumeDocument.model_fields},
        original_filename=f"generated_{user_data.get('name','resume')}.pdf",
        file_type="generated",
    )
    await new_resume.insert()
    new_id = str(new_resume.id)

    return GenerateResumeResponse(
        resume_id=new_id,
        html_content=result["html_content"],
        pdf_path=result["pdf_path"],
        download_url=result["download_url"],
        template_used=request.template,
        generated_at=__import__("datetime").datetime.utcnow(),
    )


# ─────────────────────────────────────────────────────────
# GET /resume/{resume_id}
# ─────────────────────────────────────────────────────────

@router.get(
    "/resume/{resume_id}",
    summary="Retrieve a parsed resume by ID",
)
async def get_resume(resume_id: str):
    doc = await ResumeDocument.get(resume_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Resume '{resume_id}' not found")
    return doc.dict()


# ─────────────────────────────────────────────────────────
# GET /analysis/{analysis_id}
# ─────────────────────────────────────────────────────────

@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalyzeResponse,
    summary="Retrieve a stored analysis by ID",
)
async def get_analysis(analysis_id: str):
    doc = await AnalysisDocument.get(analysis_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    return AnalyzeResponse(
        analysis_id=str(doc.id),
        resume_id=doc.resume_id,
        ats_score=doc.ats_score,
        match_percentage=doc.match_percentage,
        score_breakdown=doc.score_breakdown,
        matched_keywords=doc.matched_keywords,
        missing_keywords=doc.missing_keywords,
        missing_skills=doc.missing_skills,
        extra_skills=doc.extra_skills,
        improvement_suggestions=doc.improvement_suggestions,
        enhanced_bullets=doc.enhanced_bullets,
        missing_sections=doc.missing_sections,
        report_available=bool(doc.report_pdf_path),
        analyzed_at=doc.analyzed_at,
    )


# ─────────────────────────────────────────────────────────
# GET /download/{filename}
# ─────────────────────────────────────────────────────────

@router.get(
    "/download/{filename}",
    summary="Download a generated resume or report PDF",
)
async def download_file(filename: str):
    """Serve generated PDF files for download."""
    # Security: only serve from reports dir, no path traversal
    safe_name = Path(filename).name
    file_path = settings.REPORTS_DIR / safe_name

    if not file_path.exists():
        # Also check uploads dir
        file_path = settings.UPLOAD_DIR / safe_name
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_name,
    )
