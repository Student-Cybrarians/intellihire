"""
app/services/llm_service.py
────────────────────────────
Unified LLM service supporting OpenAI and Anthropic.

Design decisions:
  - Provider is selected from settings.LLM_PROVIDER
  - Tenacity handles retries with exponential backoff
  - All prompts are defined here (single source of truth)
  - Each method has a focused, single-responsibility prompt
"""

import json
import logging
from typing import Dict, List, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import LLMError

logger = logging.getLogger(__name__)


class LLMService:
    """
    Handles all LLM interactions for IntelliHire Module 1.

    Methods:
        suggest_improvements()  — bullet-level improvement suggestions
        enhance_bullets()       — rewrite weak bullets with metrics
        generate_summary()      — craft a professional resume summary
        generate_resume_content() — fill resume template with LLM-written content
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self._client = None

    @property
    def client(self):
        """Lazy-load the LLM client on first use."""
        if self._client is None:
            if self.provider == "openai":
                import openai
                self._client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            elif self.provider == "anthropic":
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            else:
                raise LLMError(f"Unknown LLM provider: {self.provider}")
        return self._client

    # ──────────────────────────────────────────────────────
    # Core LLM call (provider-agnostic)
    # ──────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call(self, system: str, user: str, max_tokens: int = 1000) -> str:
        """
        Internal: make one LLM call with retry logic.
        Returns raw text response.
        """
        try:
            if self.provider == "openai":
                response = await self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,   # low temp for factual suggestions
                )
                return response.choices[0].message.content.strip()

            elif self.provider == "anthropic":
                response = await self.client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"LLM call failed (provider={self.provider}): {e}")
            raise LLMError(f"LLM request failed: {str(e)}")

    # ──────────────────────────────────────────────────────
    # 1. Resume improvement suggestions
    # ──────────────────────────────────────────────────────

    async def suggest_improvements(
        self,
        parsed_resume: Dict,
        jd_text: str,
        missing_keywords: List[str],
        missing_skills: List[str],
    ) -> List[str]:
        """
        Generate prioritised, actionable improvement suggestions.
        Returns a list of strings (each suggestion on one line).
        """
        system = """You are an expert ATS resume coach and technical recruiter with 15 years of experience.
Your task is to provide specific, actionable resume improvement suggestions.
Be direct and concrete. Focus on what the candidate SHOULD ADD or CHANGE.
Return exactly 8 suggestions as a JSON array of strings. No markdown. Just valid JSON."""

        user = f"""Resume Summary:
Name: {parsed_resume.get('name', 'N/A')}
Skills: {', '.join(parsed_resume.get('skills', [])[:20])}
Experience: {len(parsed_resume.get('experience', []))} positions
Education: {len(parsed_resume.get('education', []))} entries
Sections present: {[k for k,v in parsed_resume.get('section_flags',{}).items() if v]}

Job Description (excerpt):
{jd_text[:800]}

Missing JD keywords: {', '.join(missing_keywords[:15])}
Missing skills: {', '.join(missing_skills[:10])}

Provide 8 specific, actionable improvement suggestions as a JSON array.
Example: ["Add a professional summary targeting {job_title}", "Include missing keyword 'Kubernetes' in your DevOps experience"]"""

        try:
            raw = await self._call(system, user, max_tokens=600)
            suggestions = self._parse_json_list(raw)
            return suggestions[:8]
        except Exception as e:
            logger.error(f"suggest_improvements failed: {e}")
            return [
                "Add a professional summary tailored to the target role.",
                f"Include missing keywords: {', '.join(missing_keywords[:5])}.",
                "Quantify achievements with numbers (%, $, time saved).",
                "Add a dedicated Skills section if not present.",
                "Ensure education section includes GPA if above 3.5.",
            ]

    # ──────────────────────────────────────────────────────
    # 2. Bullet point enhancer
    # ──────────────────────────────────────────────────────

    async def enhance_bullets(
        self, bullets: List[str], job_title: Optional[str] = None
    ) -> List[Dict]:
        """
        Rewrite weak resume bullets into strong, metric-driven bullets.

        Input:  ["Worked on backend APIs"]
        Output: [{"original": "Worked on backend APIs",
                  "enhanced": "Designed and shipped 12 REST APIs in FastAPI, reducing response latency by 40% and supporting 50k daily requests."}]
        """
        if not bullets:
            return []

        system = """You are a resume writing expert. Your job is to rewrite weak resume bullet points
into strong, impactful bullets using the STAR method (Situation-Task-Action-Result).

Rules:
- Start every bullet with a strong action verb (Designed, Built, Led, Reduced, Increased, Automated, etc.)
- Add specific metrics where possible (%, $, time, scale)
- Keep each bullet under 25 words
- Return valid JSON only — an array of objects with keys "original" and "enhanced"
- If a bullet is already strong, improve it slightly and keep the same structure"""

        target = f" for a {job_title}" if job_title else ""
        bullet_list = "\n".join(f"- {b}" for b in bullets[:8])  # cap at 8

        user = f"""Rewrite these resume bullet points{target}:

{bullet_list}

Return a JSON array: [{{"original": "...", "enhanced": "..."}}]"""

        try:
            raw = await self._call(system, user, max_tokens=800)
            return self._parse_json_list(raw, expect_dicts=True)
        except Exception as e:
            logger.error(f"enhance_bullets failed: {e}")
            # Return originals with a note
            return [{"original": b, "enhanced": b} for b in bullets]

    # ──────────────────────────────────────────────────────
    # 3. Professional summary generator
    # ──────────────────────────────────────────────────────

    async def generate_summary(
        self,
        parsed_resume: Dict,
        target_role: Optional[str] = None,
        jd_text: Optional[str] = None,
    ) -> str:
        """Generate a tailored 3-4 sentence professional summary."""
        system = """You are a professional resume writer. Write a concise, compelling professional summary
for a resume. It should be 3-4 sentences, ATS-optimized, and tailored to the target role.
Do NOT include phrases like 'Experienced professional' or 'Dynamic individual'. Be specific.
Return only the summary text, no quotes or labels."""

        skills_str = ", ".join(parsed_resume.get("skills", [])[:15])
        exp_str = "; ".join(
            f"{e.get('role')} at {e.get('company')}"
            for e in parsed_resume.get("experience", [])[:3]
        )
        edu = parsed_resume.get("education", [{}])
        edu_str = f"{edu[0].get('degree','')} in {edu[0].get('field','')} from {edu[0].get('institution','')}" if edu else ""

        user = f"""Candidate Profile:
Name: {parsed_resume.get('name', 'Candidate')}
Target Role: {target_role or 'Software Engineer'}
Education: {edu_str}
Experience: {exp_str}
Skills: {skills_str}
{f'Target JD (excerpt): {jd_text[:400]}' if jd_text else ''}

Write a 3-4 sentence professional summary."""

        try:
            return await self._call(system, user, max_tokens=300)
        except Exception:
            return (
                f"Results-driven {target_role or 'engineer'} with expertise in {skills_str[:100]}. "
                "Demonstrated ability to deliver high-quality software solutions in fast-paced environments."
            )

    # ──────────────────────────────────────────────────────
    # 4. Full resume content generation
    # ──────────────────────────────────────────────────────

    async def generate_resume_content(
        self,
        user_data: Dict,
        target_role: Optional[str] = None,
    ) -> Dict:
        """
        Given user-provided data, have the LLM:
          - Write/improve the summary
          - Enhance all experience bullets
          - Suggest a skills ordering

        Returns enriched user_data dict.
        """
        # Generate summary
        summary = await self.generate_summary(user_data, target_role)
        user_data["summary"] = summary

        # Enhance all experience bullets
        for exp in user_data.get("experience", []):
            if exp.get("description"):
                raw_bullets = [
                    l.strip().lstrip("•-–*").strip()
                    for l in exp["description"].split("\n")
                    if l.strip()
                ]
                if raw_bullets:
                    enhanced = await self.enhance_bullets(raw_bullets, target_role)
                    exp["enhanced_bullets"] = enhanced

        return user_data

    # ──────────────────────────────────────────────────────
    # Helper: parse JSON from LLM output safely
    # ──────────────────────────────────────────────────────

    def _parse_json_list(self, raw: str, expect_dicts: bool = False) -> List:
        """
        Robustly parse a JSON list from LLM output.
        LLMs sometimes wrap JSON in markdown code fences — strip those first.
        """
        # Strip markdown code fences
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Find the first [ ... ] block
        start = clean.find("[")
        end   = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning(f"No JSON array found in LLM output: {clean[:200]}")
            return []

        try:
            result = json.loads(clean[start:end+1])
            if not isinstance(result, list):
                return []
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e} | raw: {clean[:300]}")
            return []
