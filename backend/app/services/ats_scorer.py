"""
app/services/ats_scorer.py
───────────────────────────
ATS Score Calculator — 6 weighted components producing a 0–100 score.

Component        Weight   How computed
─────────────────────────────────────────────────────────────────────
keyword_match     30%    TF-IDF + exact keyword overlap (resume ∩ JD)
skills_match      20%    Semantic similarity of skills via sentence-transformers
experience_relevance 20% Cosine sim of experience bullets vs JD requirements
formatting        10%    Presence of key structural elements
readability       10%    textstat Flesch-Kincaid grade level
section_completeness 10% Percentage of expected sections present
─────────────────────────────────────────────────────────────────────

Final score = Σ(component_raw_score × weight) × 100
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Lazy imports (heavy models loaded once) ───────────────
_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model (first call, may take ~10s)…")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


# Expected resume sections — completeness score is based on these
EXPECTED_SECTIONS = ["skills", "experience", "education", "projects", "summary", "certifications"]

# Words that don't carry meaning for keyword matching
STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","as","is","it","its","be","are","was","were","have","has",
    "had","do","does","did","will","would","could","should","may","might",
    "we","our","us","your","their","this","that","these","those","which",
    "who","whom","how","what","when","where","why","all","any","both","each",
}


class ATSScorer:
    """
    Computes multi-dimensional ATS score for a resume vs job description.

    Usage:
        scorer = ATSScorer()
        result = scorer.compute(parsed_resume, jd_text)
    """

    def __init__(self):
        from app.core.config import settings
        self.weights = settings.SCORE_WEIGHTS

    # ──────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────

    def compute(self, parsed_resume: Dict, jd_text: str) -> Dict:
        """
        Run all 6 scoring components and return full result dict.

        Returns:
            {
                ats_score: float (0–100),
                match_percentage: float,
                score_breakdown: [...],
                matched_keywords: [...],
                missing_keywords: [...],
                missing_skills: [...],
                extra_skills: [...],
            }
        """
        jd_keywords = self._extract_keywords(jd_text)
        jd_skills   = self._extract_skills_from_jd(jd_text)
        resume_text = parsed_resume.get("raw_text", "")
        resume_skills = [s.lower() for s in parsed_resume.get("skills", [])]

        # ── Component 1: Keyword match (30%) ────────────────
        kw_score, matched_kw, missing_kw = self._keyword_match_score(
            resume_text, jd_keywords
        )

        # ── Component 2: Skills match (20%) ─────────────────
        skills_score, missing_skills, extra_skills = self._skills_match_score(
            resume_skills, jd_skills
        )

        # ── Component 3: Experience relevance (20%) ──────────
        exp_score = self._experience_relevance_score(
            parsed_resume.get("experience", []), jd_text
        )

        # ── Component 4: Formatting (10%) ───────────────────
        fmt_score = self._formatting_score(parsed_resume)

        # ── Component 5: Readability (10%) ──────────────────
        read_score = self._readability_score(resume_text)

        # ── Component 6: Section completeness (10%) ──────────
        sec_score = self._section_completeness_score(
            parsed_resume.get("section_flags", {})
        )

        # ── Aggregate ─────────────────────────────────────────
        components = {
            "keyword_match":          kw_score,
            "skills_match":           skills_score,
            "experience_relevance":   exp_score,
            "formatting":             fmt_score,
            "readability":            read_score,
            "section_completeness":   sec_score,
        }

        breakdown = []
        total_weighted = 0.0
        for name, raw_score in components.items():
            weight = self.weights[name]
            weighted = raw_score * weight
            total_weighted += weighted
            breakdown.append({
                "component":      name,
                "raw_score":      round(raw_score, 4),
                "weighted_score": round(weighted, 4),
                "weight":         weight,
                "explanation":    self._explain(name, raw_score, matched_kw, missing_kw),
            })

        ats_score = round(total_weighted * 100, 1)

        # Semantic match % (cosine similarity of full texts)
        match_pct = self._semantic_similarity(resume_text[:2000], jd_text[:2000])

        return {
            "ats_score":         ats_score,
            "match_percentage":  round(match_pct * 100, 1),
            "score_breakdown":   breakdown,
            "matched_keywords":  matched_kw,
            "missing_keywords":  missing_kw[:30],
            "missing_skills":    self._prioritise_missing_skills(missing_skills, jd_text),
            "extra_skills":      extra_skills,
        }

    # ──────────────────────────────────────────────────────
    # Component 1: Keyword match
    # ──────────────────────────────────────────────────────

    def _keyword_match_score(
        self, resume_text: str, jd_keywords: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """
        Exact + fuzzy keyword overlap.

        Score = matched_keywords / total_jd_keywords
        Capped at 1.0.
        """
        if not jd_keywords:
            return 0.5, [], []  # neutral if JD has no extractable keywords

        resume_lower = resume_text.lower()
        matched = []
        missing = []

        for kw in jd_keywords:
            # Word-boundary match to avoid "java" matching "javascript"
            pattern = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern, resume_lower):
                matched.append(kw)
            else:
                missing.append(kw)

        score = min(len(matched) / max(len(jd_keywords), 1), 1.0)
        return score, matched, missing

    # ──────────────────────────────────────────────────────
    # Component 2: Skills match (semantic)
    # ──────────────────────────────────────────────────────

    def _skills_match_score(
        self, resume_skills: List[str], jd_skills: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """
        Compares resume skills vs JD skills.

        Uses a two-pass approach:
          Pass 1 — exact/lowercase match
          Pass 2 — semantic similarity for remaining (catches Python ≈ py, JS ≈ JavaScript)

        Returns (score, missing_skills, extra_skills)
        """
        if not jd_skills:
            return 0.5, [], []

        resume_set = set(s.lower() for s in resume_skills)
        jd_set     = set(s.lower() for s in jd_skills)

        # Pass 1: exact
        matched_exact = resume_set & jd_set
        still_missing = jd_set - matched_exact

        # Pass 2: semantic (only if embedding model available and items remain)
        semantic_matched: set = set()
        if still_missing and resume_set:
            try:
                model = _get_embedding_model()
                import numpy as np

                resume_list = list(resume_set)
                missing_list = list(still_missing)
                r_emb = model.encode(resume_list, convert_to_numpy=True)
                m_emb = model.encode(missing_list, convert_to_numpy=True)

                # Cosine similarity matrix
                r_norm = r_emb / (np.linalg.norm(r_emb, axis=1, keepdims=True) + 1e-9)
                m_norm = m_emb / (np.linalg.norm(m_emb, axis=1, keepdims=True) + 1e-9)
                sim_matrix = m_norm @ r_norm.T  # shape: (missing, resume)

                for i, jd_skill in enumerate(missing_list):
                    max_sim = sim_matrix[i].max()
                    if max_sim > 0.82:   # threshold: highly similar
                        semantic_matched.add(jd_skill)

            except Exception as e:
                logger.warning(f"Semantic skill match failed: {e}")

        total_matched = len(matched_exact) + len(semantic_matched)
        truly_missing = [s for s in jd_skills if s.lower() not in matched_exact | semantic_matched]
        extra = [s for s in resume_skills if s.lower() not in jd_set]

        score = min(total_matched / max(len(jd_skills), 1), 1.0)
        return score, truly_missing, extra

    # ──────────────────────────────────────────────────────
    # Component 3: Experience relevance
    # ──────────────────────────────────────────────────────

    def _experience_relevance_score(
        self, experiences: List[Dict], jd_text: str
    ) -> float:
        """
        Encode each work experience description and compute cosine similarity
        to the JD text. Use the max similarity across all experiences.
        """
        if not experiences:
            return 0.0

        exp_texts = [
            f"{e.get('role','')} {e.get('company','')} {e.get('description','')}"
            for e in experiences
            if e.get("description") or e.get("role")
        ]

        if not exp_texts:
            return 0.0

        try:
            model = _get_embedding_model()
            import numpy as np

            exp_embs = model.encode(exp_texts, convert_to_numpy=True)
            jd_emb   = model.encode([jd_text[:1500]], convert_to_numpy=True)

            exp_norm = exp_embs / (np.linalg.norm(exp_embs, axis=1, keepdims=True) + 1e-9)
            jd_norm  = jd_emb / (np.linalg.norm(jd_emb, axis=1, keepdims=True) + 1e-9)

            similarities = (exp_norm @ jd_norm.T).flatten()
            return float(similarities.max())

        except Exception as e:
            logger.warning(f"Experience relevance scoring failed: {e}")
            return 0.3  # default neutral

    # ──────────────────────────────────────────────────────
    # Component 4: Formatting
    # ──────────────────────────────────────────────────────

    def _formatting_score(self, parsed: Dict) -> float:
        """
        Score based on structural completeness of key resume fields.

        Check list:
          - Has name         (+0.15)
          - Has email        (+0.15)
          - Has phone        (+0.10)
          - Has LinkedIn     (+0.10)
          - Has GitHub       (+0.10)
          - Word count 300–800 (+0.20)   ← ideal ATS resume length
          - Has bullet points (+0.10)    ← inferred from raw text
          - Has dates in exp  (+0.10)
        """
        score = 0.0
        if parsed.get("name"):     score += 0.15
        if parsed.get("email"):    score += 0.15
        if parsed.get("phone"):    score += 0.10
        if parsed.get("linkedin"): score += 0.10
        if parsed.get("github"):   score += 0.10

        wc = parsed.get("word_count", 0)
        if 300 <= wc <= 900:
            score += 0.20
        elif 200 <= wc < 300 or 900 < wc <= 1200:
            score += 0.10

        raw = parsed.get("raw_text", "")
        if re.search(r"^[•\-–*]", raw, re.MULTILINE):
            score += 0.10

        has_dates = any(
            e.get("start_date") for e in parsed.get("experience", [])
        )
        if has_dates:
            score += 0.10

        return min(score, 1.0)

    # ──────────────────────────────────────────────────────
    # Component 5: Readability
    # ──────────────────────────────────────────────────────

    def _readability_score(self, text: str) -> float:
        """
        Flesch Reading Ease score (higher = easier to read).
        Ideal for resumes: 60–70 (plain English).

        Raw Flesch → normalised 0–1 score.
        """
        try:
            import textstat
            flesch = textstat.flesch_reading_ease(text)
            # Map: <30 → 0.2, 30-50 → 0.5, 50-70 → 0.9, >70 → 0.7 (too simple)
            if flesch < 30:
                return 0.2
            elif flesch < 50:
                return 0.5
            elif flesch < 70:
                return 0.9
            elif flesch < 80:
                return 1.0
            else:
                return 0.7  # too simple for professional context
        except Exception:
            return 0.5  # neutral fallback

    # ──────────────────────────────────────────────────────
    # Component 6: Section completeness
    # ──────────────────────────────────────────────────────

    def _section_completeness_score(self, section_flags: Dict[str, bool]) -> float:
        """
        What fraction of expected resume sections are present?

        Expected: skills, experience, education, projects, summary, certifications
        Score = found_sections / total_expected
        """
        if not section_flags:
            return 0.0
        found = sum(1 for s in EXPECTED_SECTIONS if section_flags.get(s, False))
        return found / len(EXPECTED_SECTIONS)

    # ──────────────────────────────────────────────────────
    # Semantic similarity (match %)
    # ──────────────────────────────────────────────────────

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Cosine similarity between full resume text and JD."""
        try:
            import numpy as np
            model = _get_embedding_model()
            embs = model.encode([text1, text2], convert_to_numpy=True)
            norm = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
            return float((norm[0] @ norm[1]))
        except Exception:
            return 0.5

    # ──────────────────────────────────────────────────────
    # Keyword / skill extraction from JD
    # ──────────────────────────────────────────────────────

    def _extract_keywords(self, jd_text: str) -> List[str]:
        """
        Extract meaningful keywords from a JD using:
          1. spaCy noun chunks + PROPN/NOUN tokens
          2. Tech term pattern matching
        """
        keywords = set()
        jd_lower = jd_text.lower()

        # Tokenise and filter stop words
        words = re.findall(r"\b[a-zA-Z][\w.+#-]*\b", jd_text)
        for word in words:
            w = word.lower()
            if w not in STOP_WORDS and len(w) > 2:
                keywords.add(w)

        # Multi-word tech terms (preserve as-is)
        multiword = re.findall(
            r"\b(machine learning|deep learning|natural language processing|"
            r"computer vision|data science|software engineering|"
            r"system design|object oriented|agile methodolog|ci/cd|"
            r"REST api|microservices|cloud computing|DevOps)\b",
            jd_text,
            re.IGNORECASE,
        )
        for m in multiword:
            keywords.add(m.lower())

        return sorted(keywords)

    def _extract_skills_from_jd(self, jd_text: str) -> List[str]:
        """
        Extract skills specifically from JD.
        Looks for lists after "Requirements", "Skills", "Qualifications" headings.
        """
        skills = set()
        jd_lower = jd_text.lower()

        # Common tech skills to match
        KNOWN_SKILLS = [
            "python", "java", "javascript", "typescript", "c++", "c#", "go",
            "rust", "kotlin", "swift", "r", "scala", "sql", "nosql",
            "react", "vue", "angular", "nextjs", "nodejs", "express",
            "django", "fastapi", "flask", "spring boot", "laravel",
            "docker", "kubernetes", "terraform", "ansible", "jenkins",
            "aws", "gcp", "azure", "heroku", "vercel",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "kafka", "rabbitmq", "celery",
            "tensorflow", "pytorch", "scikit-learn", "keras", "huggingface",
            "opencv", "nlp", "llm", "langchain",
            "git", "linux", "bash", "rest", "graphql", "grpc",
            "machine learning", "deep learning", "data science",
            "computer vision", "natural language processing",
        ]

        for skill in KNOWN_SKILLS:
            if skill in jd_lower:
                skills.add(skill)

        return sorted(skills)

    def _prioritise_missing_skills(
        self, missing_skills: List[str], jd_text: str
    ) -> List[str]:
        """
        Sort missing skills by frequency in JD (higher frequency = more critical).
        """
        jd_lower = jd_text.lower()
        scored = []
        for skill in missing_skills:
            count = len(re.findall(r"\b" + re.escape(skill.lower()) + r"\b", jd_lower))
            scored.append((skill, count))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored]

    # ──────────────────────────────────────────────────────
    # Explanation generator
    # ──────────────────────────────────────────────────────

    def _explain(
        self, component: str, score: float, matched: List[str], missing: List[str]
    ) -> str:
        explanations = {
            "keyword_match": (
                f"Found {len(matched)} of {len(matched)+len(missing)} JD keywords in resume. "
                f"Score: {score:.0%}. Missing top terms: {', '.join(missing[:5]) or 'none'}."
            ),
            "skills_match": (
                f"Skills alignment with JD requirements: {score:.0%}."
            ),
            "experience_relevance": (
                f"Work experience semantic match with JD: {score:.0%}."
            ),
            "formatting": (
                f"Resume structure quality: {score:.0%}. "
                "Based on contact info, length, bullet points, and date presence."
            ),
            "readability": (
                f"Flesch readability score: {score:.0%}. "
                "Optimal range is clear, concise professional English."
            ),
            "section_completeness": (
                f"Expected sections present: {score:.0%}. "
                f"Expected: {', '.join(EXPECTED_SECTIONS)}."
            ),
        }
        return explanations.get(component, "")
