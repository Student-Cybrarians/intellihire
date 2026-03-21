"""
tests/test_parser.py
─────────────────────
Unit tests for the ResumeParser.

Run with:  pytest tests/test_parser.py -v
"""

import pytest
from app.parsers.resume_parser import ResumeParser

parser = ResumeParser()


# ── Fixtures ─────────────────────────────────────────────

SAMPLE_RESUME_TEXT = """
John Doe
john.doe@email.com | +91-9876543210 | linkedin.com/in/johndoe | github.com/johndoe
Bengaluru, Karnataka

SUMMARY
Results-driven software engineer with 3 years of experience in Python, FastAPI, and cloud-native development.

SKILLS
Python, FastAPI, Django, React, Node.js, PostgreSQL, MongoDB, Docker, Kubernetes, AWS, GCP, Git, Linux, Redis

EXPERIENCE
Software Engineer | Infosys | Jan 2022 – Present
• Built and deployed 5 REST APIs using FastAPI, reducing response time by 35%
• Automated CI/CD pipeline using GitHub Actions and Docker, cutting deployment time by 60%
• Led migration of monolithic app to microservices, improving system uptime to 99.9%

Software Developer Intern | TCS | Jun 2021 – Dec 2021
• Developed internal dashboard using React and Node.js serving 500+ daily users
• Optimised SQL queries reducing page load time by 40%

EDUCATION
B.Tech in Computer Science and Engineering
Visvesvaraya Technological University | 2021 | GPA: 8.7/10

PROJECTS
IntelliHire – AI Placement Trainer
Built a full-stack AI-powered placement prep platform using Python, FastAPI, LangChain, and React.
https://github.com/johndoe/intellihire

E-Commerce Microservices Platform
Designed and implemented 8 microservices with Docker and Kubernetes. Technologies: Go, PostgreSQL, Redis.

CERTIFICATIONS
AWS Certified Developer – Associate (2023)
Google Cloud Professional Data Engineer (2022)
"""


def make_pdf_bytes(text: str) -> bytes:
    """Create a minimal valid PDF bytes from text for testing."""
    # We test text parsing logic — use the DOCX path with a fake text "file"
    # Real PDF bytes test would need a real PDF fixture
    return text.encode("utf-8")


# ── Tests: contact extraction ─────────────────────────────

class TestContactExtraction:

    def _parse(self, text: str) -> dict:
        """Parse text through the DOCX path (text-based, no binary needed)."""
        # Inject raw_text directly to test extraction methods
        sections = parser._detect_sections(text)
        return parser._extract_contact_info(text)

    def test_email_extracted(self):
        result = self._parse(SAMPLE_RESUME_TEXT)
        assert result["email"] == "john.doe@email.com"

    def test_phone_extracted(self):
        result = self._parse(SAMPLE_RESUME_TEXT)
        assert "+91" in result["phone"] or "9876543210" in result["phone"]

    def test_linkedin_extracted(self):
        result = self._parse(SAMPLE_RESUME_TEXT)
        assert result["linkedin"] is not None
        assert "johndoe" in result["linkedin"]

    def test_github_extracted(self):
        result = self._parse(SAMPLE_RESUME_TEXT)
        assert result["github"] is not None
        assert "johndoe" in result["github"]

    def test_email_missing(self):
        result = self._parse("John Smith\n+1-555-0100\nNo email here")
        assert result["email"] == ""

    def test_no_crash_on_empty(self):
        result = self._parse("")
        assert isinstance(result, dict)
        assert result["email"] == ""


# ── Tests: section detection ──────────────────────────────

class TestSectionDetection:

    def test_skills_section_detected(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        assert "skills" in sections
        assert "Python" in sections["skills"]

    def test_experience_section_detected(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        assert "experience" in sections

    def test_education_section_detected(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        assert "education" in sections

    def test_projects_section_detected(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        assert "projects" in sections

    def test_certifications_section_detected(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        assert "certifications" in sections


# ── Tests: skills extraction ──────────────────────────────

class TestSkillsExtraction:

    def test_skills_extracted(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        skills = parser._extract_skills(sections, SAMPLE_RESUME_TEXT)
        assert len(skills) > 0
        skill_lower = [s.lower() for s in skills]
        assert "python" in skill_lower

    def test_skills_deduplicated(self):
        text = "Skills: Python, Python, JavaScript, python"
        sections = {"skills": text}
        skills = parser._extract_skills(sections, text)
        skill_lower = [s.lower() for s in skills]
        assert skill_lower.count("python") == 1

    def test_skills_capped_at_80(self):
        many = ", ".join([f"skill_{i}" for i in range(200)])
        sections = {"skills": many}
        skills = parser._extract_skills(sections, many)
        assert len(skills) <= 80


# ── Tests: experience extraction ─────────────────────────

class TestExperienceExtraction:

    def test_experience_count(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        experiences = parser._extract_experience(sections)
        assert len(experiences) >= 1

    def test_experience_has_role(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        experiences = parser._extract_experience(sections)
        assert any(exp.get("role") for exp in experiences)

    def test_experience_empty_text(self):
        result = parser._extract_experience({})
        assert result == []


# ── Tests: education extraction ───────────────────────────

class TestEducationExtraction:

    def test_education_extracted(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        edu = parser._extract_education(sections)
        assert len(edu) >= 1

    def test_education_has_degree(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        edu = parser._extract_education(sections)
        assert any(e.get("degree") for e in edu)

    def test_gpa_extracted(self):
        sections = parser._detect_sections(SAMPLE_RESUME_TEXT)
        edu = parser._extract_education(sections)
        gpas = [e.get("gpa") for e in edu if e.get("gpa")]
        assert len(gpas) >= 1


# ── Tests: text cleaning ──────────────────────────────────

class TestTextCleaning:

    def test_clean_text_collapses_newlines(self):
        text = "Hello\n\n\n\n\nWorld"
        result = parser._clean_text(text)
        assert "\n\n\n" not in result

    def test_clean_text_collapses_spaces(self):
        text = "Hello     World"
        result = parser._clean_text(text)
        assert "  " not in result

    def test_clean_text_strips(self):
        text = "   Hello World   "
        result = parser._clean_text(text)
        assert result == "Hello World"


# ── Tests: edge cases ────────────────────────────────────

class TestEdgeCases:

    def test_empty_resume_raises(self):
        from app.core.exceptions import EmptyResumeError
        with pytest.raises(EmptyResumeError):
            parser.parse(file_bytes=b"", file_type="docx")

    def test_unsupported_type_raises(self):
        from app.core.exceptions import ResumeParseError
        with pytest.raises(ResumeParseError):
            parser.parse(file_bytes=b"some content", file_type="xlsx")

    def test_very_short_text_raises(self):
        from app.core.exceptions import EmptyResumeError
        with pytest.raises(EmptyResumeError):
            parser.parse(file_bytes=b"Hi", file_type="docx")
