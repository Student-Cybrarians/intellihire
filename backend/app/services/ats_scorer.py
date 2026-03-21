"""
app/services/ats_scorer.py
Lightweight version — uses scikit-learn TF-IDF instead of sentence-transformers.
No C-compilation. Works on Render free tier.
"""
import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

EXPECTED_SECTIONS = ["skills","experience","education","projects","summary","certifications"]

STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by","from",
    "as","is","it","be","are","was","were","have","has","had","do","does","did","will",
    "would","could","should","we","our","us","your","this","that","these","those","not","no",
}

KNOWN_SKILLS = [
    "python","java","javascript","typescript","c++","c#","go","rust","kotlin","swift","sql",
    "react","vue","angular","nextjs","nodejs","express","django","fastapi","flask","spring",
    "docker","kubernetes","terraform","ansible","jenkins","aws","gcp","azure",
    "postgresql","mysql","mongodb","redis","elasticsearch","kafka",
    "tensorflow","pytorch","scikit-learn","keras","huggingface","opencv","nlp","llm","langchain",
    "git","linux","bash","rest","graphql","machine learning","deep learning","data science",
    "computer vision","natural language processing","ci/cd","microservices","devops",
]


class ATSScorer:
    def __init__(self):
        from app.core.config import settings
        self.weights = settings.SCORE_WEIGHTS

    def compute(self, parsed_resume: Dict, jd_text: str) -> Dict:
        jd_keywords = self._extract_keywords(jd_text)
        jd_skills   = self._extract_skills_from_jd(jd_text)
        resume_text = parsed_resume.get("raw_text", "")
        resume_skills = [s.lower() for s in parsed_resume.get("skills", [])]

        kw_score, matched_kw, missing_kw = self._keyword_match_score(resume_text, jd_keywords)
        skills_score, missing_skills, extra_skills = self._skills_match_score(resume_skills, jd_skills)
        exp_score   = self._experience_relevance_score(parsed_resume.get("experience", []), jd_text)
        fmt_score   = self._formatting_score(parsed_resume)
        read_score  = self._readability_score(resume_text)
        sec_score   = self._section_completeness_score(parsed_resume.get("section_flags", {}))

        components = {
            "keyword_match": kw_score, "skills_match": skills_score,
            "experience_relevance": exp_score, "formatting": fmt_score,
            "readability": read_score, "section_completeness": sec_score,
        }
        breakdown = []
        total = 0.0
        for name, raw in components.items():
            w = self.weights[name]
            wt = raw * w
            total += wt
            breakdown.append({
                "component": name, "raw_score": round(raw, 4),
                "weighted_score": round(wt, 4), "weight": w,
                "explanation": self._explain(name, raw, matched_kw, missing_kw),
            })

        match_pct = self._tfidf_similarity(resume_text[:2000], jd_text[:2000])
        return {
            "ats_score": round(total * 100, 1),
            "match_percentage": round(match_pct * 100, 1),
            "score_breakdown": breakdown,
            "matched_keywords": matched_kw,
            "missing_keywords": missing_kw[:30],
            "missing_skills": self._prioritise(missing_skills, jd_text),
            "extra_skills": extra_skills,
        }

    def _keyword_match_score(self, resume_text: str, jd_keywords: List[str]) -> Tuple[float, List[str], List[str]]:
        if not jd_keywords:
            return 0.5, [], []
        resume_lower = resume_text.lower()
        matched, missing = [], []
        for kw in jd_keywords:
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", resume_lower):
                matched.append(kw)
            else:
                missing.append(kw)
        return min(len(matched) / max(len(jd_keywords), 1), 1.0), matched, missing

    def _skills_match_score(self, resume_skills: List[str], jd_skills: List[str]) -> Tuple[float, List[str], List[str]]:
        if not jd_skills:
            return 0.5, [], []
        resume_set = set(resume_skills)
        jd_set = set(jd_skills)
        matched = resume_set & jd_set
        missing = [s for s in jd_skills if s not in matched]
        extra = [s for s in resume_skills if s not in jd_set]
        score = min(len(matched) / max(len(jd_skills), 1), 1.0)
        return score, missing, extra

    def _experience_relevance_score(self, experiences: List[Dict], jd_text: str) -> float:
        if not experiences:
            return 0.0
        exp_text = " ".join(
            f"{e.get('role','')} {e.get('company','')} {e.get('description','')}"
            for e in experiences
        )
        return self._tfidf_similarity(exp_text[:1500], jd_text[:1500])

    def _tfidf_similarity(self, text1: str, text2: str) -> float:
        """Cosine similarity using scikit-learn TF-IDF — no GPU/compilation needed."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            if not text1.strip() or not text2.strip():
                return 0.5
            vect = TfidfVectorizer(stop_words="english", max_features=500)
            tfidf = vect.fit_transform([text1, text2])
            score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            return float(score)
        except Exception as e:
            logger.warning(f"TF-IDF similarity failed: {e}")
            return 0.5

    def _formatting_score(self, parsed: Dict) -> float:
        score = 0.0
        if parsed.get("name"):     score += 0.15
        if parsed.get("email"):    score += 0.15
        if parsed.get("phone"):    score += 0.10
        if parsed.get("linkedin"): score += 0.10
        if parsed.get("github"):   score += 0.10
        wc = parsed.get("word_count", 0)
        if 300 <= wc <= 900: score += 0.20
        elif 150 <= wc < 300: score += 0.10
        if re.search(r"^[•\-–*]", parsed.get("raw_text",""), re.MULTILINE): score += 0.10
        if any(e.get("start_date") for e in parsed.get("experience", [])): score += 0.10
        return min(score, 1.0)

    def _readability_score(self, text: str) -> float:
        try:
            import textstat
            flesch = textstat.flesch_reading_ease(text)
            if flesch < 30: return 0.2
            elif flesch < 50: return 0.5
            elif flesch < 70: return 0.9
            elif flesch < 80: return 1.0
            else: return 0.7
        except Exception:
            return 0.5

    def _section_completeness_score(self, section_flags: Dict) -> float:
        if not section_flags:
            return 0.0
        found = sum(1 for s in EXPECTED_SECTIONS if section_flags.get(s, False))
        return found / len(EXPECTED_SECTIONS)

    def _extract_keywords(self, jd_text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z][\w+#.-]*\b", jd_text.lower())
        return sorted(set(w for w in words if w not in STOP_WORDS and len(w) > 2))

    def _extract_skills_from_jd(self, jd_text: str) -> List[str]:
        jd_lower = jd_text.lower()
        return [s for s in KNOWN_SKILLS if s in jd_lower]

    def _prioritise(self, missing: List[str], jd_text: str) -> List[str]:
        jd_lower = jd_text.lower()
        scored = [(s, len(re.findall(r"\b"+re.escape(s)+r"\b", jd_lower))) for s in missing]
        return [s for s, _ in sorted(scored, key=lambda x: x[1], reverse=True)]

    def _explain(self, component: str, score: float, matched: List[str], missing: List[str]) -> str:
        exps = {
            "keyword_match": f"Found {len(matched)} of {len(matched)+len(missing)} JD keywords. Score: {score:.0%}. Missing: {', '.join(missing[:5]) or 'none'}.",
            "skills_match": f"Skills alignment with JD: {score:.0%}.",
            "experience_relevance": f"Work experience semantic match with JD: {score:.0%}.",
            "formatting": f"Resume structure quality: {score:.0%}. Based on contact info, length, bullets.",
            "readability": f"Readability score: {score:.0%}. Optimal = clear professional English.",
            "section_completeness": f"Expected sections present: {score:.0%}. Expected: {', '.join(EXPECTED_SECTIONS)}.",
        }
        return exps.get(component, "")
