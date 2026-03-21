"""
app/services/analysis_service.py
──────────────────────────────────
Orchestrates the full ATS analysis pipeline.

Flow:
  1. Load parsed resume from MongoDB
  2. Run ATSScorer (keyword + semantic scoring)
  3. Run LLMService (improvement suggestions + bullet enhancement)
  4. Persist AnalysisDocument to MongoDB
  5. Trigger report generation (JSON + PDF)
  6. Return structured response
"""

import logging
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError
from app.models.analysis import AnalysisDocument, JobDescriptionDocument
from app.models.resume import ResumeDocument
from app.schemas.resume import AnalyzeRequest, AnalyzeResponse
from app.services.ats_scorer import ATSScorer
from app.services.llm_service import LLMService
from app.reports.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Coordinates resume analysis — the main business logic orchestrator.
    Called by the /analyze endpoint.
    """

    def __init__(self):
        self.scorer   = ATSScorer()
        self.llm      = LLMService()
        self.reporter = ReportGenerator()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        Full analysis pipeline.

        Raises:
            DocumentNotFoundError — if resume_id is invalid
            LLMError             — if LLM calls fail after retries
        """

        # ── Step 1: Load resume ──────────────────────────────
        resume_doc = await ResumeDocument.get(request.resume_id)
        if not resume_doc:
            raise DocumentNotFoundError(request.resume_id)

        parsed_resume = resume_doc.dict()
        logger.info(f"Analyzing resume: {resume_doc.name} | id={request.resume_id}")

        # ── Step 2: Persist JD ────────────────────────────────
        jd_doc = JobDescriptionDocument(
            title=request.job_title or "Unknown Role",
            company=request.company_name,
            raw_text=request.job_description,
        )
        await jd_doc.insert()

        # ── Step 3: ATS Scoring ───────────────────────────────
        logger.info("Running ATS scorer…")
        scoring_result = self.scorer.compute(
            parsed_resume=parsed_resume,
            jd_text=request.job_description,
        )

        # ── Step 4: LLM Suggestions ───────────────────────────
        improvement_suggestions = []
        enhanced_bullets = []

        logger.info("Running LLM suggestions…")
        improvement_suggestions = await self.llm.suggest_improvements(
            parsed_resume=parsed_resume,
            jd_text=request.job_description,
            missing_keywords=scoring_result["missing_keywords"],
            missing_skills=scoring_result["missing_skills"],
        )

        # Enhance bullets (optional, based on request flag)
        if request.enhance_bullets:
            raw_bullets = self._extract_all_bullets(parsed_resume)
            if raw_bullets:
                enhanced_bullets = await self.llm.enhance_bullets(
                    bullets=raw_bullets[:6],  # top 6 bullets
                    job_title=request.job_title,
                )

        # Identify missing sections
        section_flags = parsed_resume.get("section_flags", {})
        missing_sections = [
            s for s in ["summary", "skills", "experience", "education", "projects"]
            if not section_flags.get(s, False)
        ]

        # ── Step 5: Persist analysis ──────────────────────────
        analysis_doc = AnalysisDocument(
            resume_id=request.resume_id,
            jd_id=str(jd_doc.id),
            ats_score=scoring_result["ats_score"],
            match_percentage=scoring_result["match_percentage"],
            score_breakdown=scoring_result["score_breakdown"],
            matched_keywords=scoring_result["matched_keywords"],
            missing_keywords=scoring_result["missing_keywords"],
            missing_skills=scoring_result["missing_skills"],
            extra_skills=scoring_result["extra_skills"],
            improvement_suggestions=improvement_suggestions,
            enhanced_bullets=enhanced_bullets,
            missing_sections=missing_sections,
            llm_model_used=f"{settings.LLM_PROVIDER}:{settings.OPENAI_MODEL if settings.LLM_PROVIDER == 'openai' else settings.ANTHROPIC_MODEL}",
        )
        await analysis_doc.insert()
        analysis_id = str(analysis_doc.id)

        # ── Step 6: Generate reports ──────────────────────────
        report_paths = await self.reporter.generate(
            analysis_id=analysis_id,
            resume_doc=resume_doc.dict(),
            scoring_result=scoring_result,
            suggestions=improvement_suggestions,
            enhanced_bullets=enhanced_bullets,
        )

        # Update analysis with report paths
        await analysis_doc.set({
            AnalysisDocument.report_json_path: report_paths.get("json"),
            AnalysisDocument.report_pdf_path:  report_paths.get("pdf"),
        })

        logger.info(
            f"Analysis complete | id={analysis_id} | "
            f"ATS={scoring_result['ats_score']} | Match={scoring_result['match_percentage']}%"
        )

        # ── Step 7: Build response ────────────────────────────
        return AnalyzeResponse(
            analysis_id=analysis_id,
            resume_id=request.resume_id,
            ats_score=scoring_result["ats_score"],
            match_percentage=scoring_result["match_percentage"],
            score_breakdown=scoring_result["score_breakdown"],
            matched_keywords=scoring_result["matched_keywords"],
            missing_keywords=scoring_result["missing_keywords"],
            missing_skills=scoring_result["missing_skills"],
            extra_skills=scoring_result["extra_skills"],
            improvement_suggestions=improvement_suggestions,
            enhanced_bullets=enhanced_bullets,
            missing_sections=missing_sections,
            report_available=bool(report_paths),
            analyzed_at=datetime.utcnow(),
        )

    def _extract_all_bullets(self, parsed: dict) -> list:
        """Collect all bullet points from experience descriptions."""
        bullets = []
        for exp in parsed.get("experience", []):
            desc = exp.get("description", "")
            for line in desc.split("\n"):
                line = line.strip().lstrip("•-–*").strip()
                if len(line) > 15:
                    bullets.append(line)
        return bullets
