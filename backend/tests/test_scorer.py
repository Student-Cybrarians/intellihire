"""
tests/test_scorer.py
─────────────────────
Unit tests for the ATSScorer.

Run with:  pytest tests/test_scorer.py -v
"""

import pytest
from app.services.ats_scorer import ATSScorer

scorer = ATSScorer()

SAMPLE_JD = """
We are looking for a Senior Software Engineer with the following skills:
- 3+ years of experience with Python and FastAPI
- Strong knowledge of Docker and Kubernetes
- Experience with PostgreSQL and Redis
- Familiarity with AWS or GCP cloud platforms
- Understanding of microservices architecture
- Experience with CI/CD pipelines (GitHub Actions, Jenkins)
- Strong problem-solving and communication skills
Requirements: machine learning experience is a plus, LLM, NLP, PyTorch
"""

STRONG_RESUME = {
    "raw_text": """
        Python FastAPI Docker Kubernetes PostgreSQL Redis AWS GCP
        CI/CD GitHub Actions microservices machine learning NLP PyTorch
        Software Engineer at Acme Corp Jan 2021 - Present
        Built REST APIs using FastAPI serving 100k users
        Deployed microservices on Kubernetes reducing costs by 30%
    """,
    "skills": ["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "Redis", "AWS", "GCP", "CI/CD"],
    "experience": [
        {
            "role": "Software Engineer",
            "company": "Acme Corp",
            "start_date": "Jan 2021",
            "end_date": "Present",
            "description": "Built REST APIs using FastAPI serving 100k users. Deployed microservices on Kubernetes.",
        }
    ],
    "education": [{"degree": "B.Tech", "field": "CSE", "institution": "IIT Delhi", "year": "2021"}],
    "section_flags": {
        "skills": True, "experience": True, "education": True,
        "projects": True, "summary": True, "certifications": True,
    },
    "word_count": 450,
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+91-9876543210",
    "linkedin": "linkedin.com/in/janedoe",
    "github": "github.com/janedoe",
}

WEAK_RESUME = {
    "raw_text": "Java PHP WordPress CSS HTML helped with website",
    "skills": ["Java", "PHP", "WordPress"],
    "experience": [],
    "education": [],
    "section_flags": {},
    "word_count": 50,
    "name": "",
    "email": "",
    "phone": "",
    "linkedin": None,
    "github": None,
}


class TestATSScorer:

    def test_strong_resume_scores_higher(self):
        strong = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        weak   = scorer.compute(WEAK_RESUME, SAMPLE_JD)
        assert strong["ats_score"] > weak["ats_score"]

    def test_ats_score_in_range(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        assert 0 <= result["ats_score"] <= 100

    def test_match_percentage_in_range(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        assert 0 <= result["match_percentage"] <= 100

    def test_matched_keywords_is_list(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        assert isinstance(result["matched_keywords"], list)

    def test_missing_keywords_is_list(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        assert isinstance(result["missing_keywords"], list)

    def test_missing_skills_is_list(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        assert isinstance(result["missing_skills"], list)

    def test_score_breakdown_has_6_components(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        assert len(result["score_breakdown"]) == 6

    def test_weights_sum_to_one(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        total_weight = sum(c["weight"] for c in result["score_breakdown"])
        assert abs(total_weight - 1.0) < 0.001

    def test_weighted_scores_sum_to_ats_score(self):
        result = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        weighted_sum = sum(c["weighted_score"] for c in result["score_breakdown"])
        assert abs(weighted_sum * 100 - result["ats_score"]) < 0.5

    def test_weak_resume_has_missing_skills(self):
        result = scorer.compute(WEAK_RESUME, SAMPLE_JD)
        assert len(result["missing_skills"]) > 0

    def test_strong_resume_has_fewer_missing_skills(self):
        strong = scorer.compute(STRONG_RESUME, SAMPLE_JD)
        weak   = scorer.compute(WEAK_RESUME, SAMPLE_JD)
        assert len(strong["missing_skills"]) < len(weak["missing_skills"])


class TestKeywordExtraction:

    def test_extracts_tech_keywords(self):
        kws = scorer._extract_keywords(SAMPLE_JD)
        kw_lower = [k.lower() for k in kws]
        assert "python" in kw_lower or "fastapi" in kw_lower

    def test_extracts_skills_from_jd(self):
        skills = scorer._extract_skills_from_jd(SAMPLE_JD)
        assert "python" in skills or "docker" in skills

    def test_empty_jd_returns_neutral_score(self):
        result = scorer.compute(STRONG_RESUME, "  ")
        # Should not crash; returns some score
        assert 0 <= result["ats_score"] <= 100


class TestFormattingScore:

    def test_full_contact_scores_higher(self):
        full = scorer._formatting_score(STRONG_RESUME)
        empty = scorer._formatting_score(WEAK_RESUME)
        assert full > empty

    def test_ideal_word_count_rewarded(self):
        resume_ideal = {**WEAK_RESUME, "word_count": 500}
        resume_short = {**WEAK_RESUME, "word_count": 50}
        assert scorer._formatting_score(resume_ideal) > scorer._formatting_score(resume_short)


class TestReadabilityScore:

    def test_readable_text_scores_well(self):
        readable_text = (
            "Built REST APIs in Python. Led a team of five engineers. "
            "Reduced latency by 30 percent using caching. Deployed on AWS."
        ) * 10
        score = scorer._readability_score(readable_text)
        assert 0.3 <= score <= 1.0

    def test_empty_text_returns_neutral(self):
        score = scorer._readability_score("")
        assert score == 0.5


class TestSectionCompletenessScore:

    def test_all_sections_full_score(self):
        flags = {s: True for s in ["skills", "experience", "education", "projects", "summary", "certifications"]}
        score = scorer._section_completeness_score(flags)
        assert score == 1.0

    def test_no_sections_zero_score(self):
        score = scorer._section_completeness_score({})
        assert score == 0.0

    def test_partial_sections_partial_score(self):
        flags = {"skills": True, "experience": True, "education": True}
        score = scorer._section_completeness_score(flags)
        assert 0 < score < 1.0
