"""
app/services/llm_service.py — Microsoft Azure OpenAI
Primary: Azure OpenAI (GPT-4o via Azure)
Fallback: Standard OpenAI API
"""
import json
import logging
from typing import Dict, List, Optional
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from app.core.config import settings
from app.core.exceptions import LLMError

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if self.provider == "azure_openai" and settings.AZURE_OPENAI_API_KEY:
                from openai import AsyncAzureOpenAI
                self._client = AsyncAzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                )
            else:
                # Fallback to standard OpenAI
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def _call(self, system: str, user: str, max_tokens: int = 1000) -> str:
        try:
            model = (settings.AZURE_OPENAI_DEPLOYMENT
                     if self.provider == "azure_openai"
                     else settings.OPENAI_MODEL)
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Azure OpenAI call failed: {e}")
            raise LLMError(f"LLM request failed: {str(e)}")

    async def suggest_improvements(self, parsed_resume: Dict, jd_text: str,
                                   missing_keywords: List[str], missing_skills: List[str]) -> List[str]:
        system = """You are an expert ATS resume coach. Provide 8 specific, actionable resume improvement suggestions.
Return exactly 8 suggestions as a JSON array of strings. No markdown. Just valid JSON."""
        user = f"""Resume: {parsed_resume.get('name','N/A')} | Skills: {', '.join(parsed_resume.get('skills',[])[:15])}
JD excerpt: {jd_text[:600]}
Missing keywords: {', '.join(missing_keywords[:12])}
Missing skills: {', '.join(missing_skills[:8])}
Return 8 suggestions as JSON array."""
        try:
            raw = await self._call(system, user, 600)
            return self._parse_json_list(raw)[:8]
        except Exception as e:
            logger.error(f"suggest_improvements failed: {e}")
            return [
                "Add a professional summary targeting the role.",
                f"Include missing keywords: {', '.join(missing_keywords[:4])}.",
                "Quantify achievements with numbers (%, $, time saved).",
                "Add a Skills section if not present.",
                "Use strong action verbs: Architected, Engineered, Reduced.",
                "Add LinkedIn and GitHub profile links.",
                "Include relevant certifications.",
                "Tailor each bullet point to match JD requirements.",
            ]

    async def enhance_bullets(self, bullets: List[str], job_title: Optional[str] = None) -> List[Dict]:
        if not bullets:
            return []
        system = """You are a resume writing expert. Rewrite weak bullet points into strong, metric-driven bullets.
Start with action verbs. Add specific metrics. Keep under 25 words.
Return valid JSON array: [{"original": "...", "enhanced": "..."}]"""
        user = f"""Rewrite these resume bullets{' for ' + job_title if job_title else ''}:
{chr(10).join('- ' + b for b in bullets[:6])}
Return JSON array only."""
        try:
            raw = await self._call(system, user, 700)
            return self._parse_json_list(raw, expect_dicts=True)
        except Exception:
            return [{"original": b, "enhanced": b} for b in bullets]

    async def generate_summary(self, parsed_resume: Dict, target_role: Optional[str] = None,
                               jd_text: Optional[str] = None) -> str:
        system = """Write a concise 3-4 sentence professional resume summary. ATS-optimized.
No generic phrases. Be specific. Return only the summary text."""
        skills = ", ".join(parsed_resume.get("skills", [])[:12])
        user = f"""Name: {parsed_resume.get('name','Candidate')} | Role: {target_role or 'Software Engineer'}
Skills: {skills}
{('JD excerpt: ' + jd_text[:300]) if jd_text else ''}
Write a 3-4 sentence professional summary."""
        try:
            return await self._call(system, user, 250)
        except Exception:
            return f"Results-driven {target_role or 'engineer'} with expertise in {skills[:80]}."

    async def generate_resume_content(self, user_data: Dict, target_role: Optional[str] = None) -> Dict:
        user_data["summary"] = await self.generate_summary(user_data, target_role)
        for exp in user_data.get("experience", []):
            if exp.get("description"):
                raw_bullets = [l.strip().lstrip("•-–*").strip() for l in exp["description"].split("\n") if l.strip()]
                if raw_bullets:
                    exp["enhanced_bullets"] = await self.enhance_bullets(raw_bullets, target_role)
        return user_data

    def _parse_json_list(self, raw: str, expect_dicts: bool = False) -> List:
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        start, end = clean.find("["), clean.rfind("]")
        if start == -1 or end == -1:
            return []
        try:
            result = json.loads(clean[start:end+1])
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []
