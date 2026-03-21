"""
app/parsers/resume_parser.py
Lightweight version — uses NLTK + regex instead of spaCy.
No C-compilation dependencies. Works on Render free tier.
"""
import io
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from docx import Document as DocxDocument
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

SECTION_PATTERNS: Dict[str, List[str]] = {
    "summary":        [r"\b(summary|objective|profile|about me|professional summary)\b"],
    "skills":         [r"\b(skills?|technical skills?|core competencies|expertise|technologies)\b"],
    "experience":     [r"\b(experience|work experience|employment|professional experience|career)\b"],
    "education":      [r"\b(education|academic|qualification|degree|university|college)\b"],
    "projects":       [r"\b(projects?|personal projects?|academic projects?|portfolio)\b"],
    "certifications": [r"\b(certifications?|certificates?|licenses?|accreditations?)\b"],
    "languages":      [r"\b(languages?|language proficiency)\b"],
    "achievements":   [r"\b(achievements?|awards?|honors?|accomplishments?)\b"],
}


class ResumeParser:
    def parse(self, file_bytes: bytes, file_type: str) -> Dict:
        from app.core.exceptions import EmptyResumeError, ResumeParseError
        file_type = file_type.lower().strip(".")
        if file_type == "pdf":
            raw_text = self._extract_pdf(file_bytes)
        elif file_type in ("docx", "doc"):
            raw_text = self._extract_docx(file_bytes)
        else:
            raise ResumeParseError(f"Unsupported file type: {file_type}")
        if not raw_text or len(raw_text.strip()) < 50:
            raise EmptyResumeError()
        sections = self._detect_sections(raw_text)
        return {
            "raw_text": raw_text,
            "word_count": len(raw_text.split()),
            "char_count": len(raw_text),
            "section_flags": {k: bool(v) for k, v in sections.items()},
            **self._extract_contact_info(raw_text),
            "summary":        self._extract_summary(sections),
            "skills":         self._extract_skills(sections, raw_text),
            "soft_skills":    self._extract_soft_skills(raw_text),
            "experience":     self._extract_experience(sections),
            "education":      self._extract_education(sections),
            "projects":       self._extract_projects(sections),
            "certifications": self._extract_certifications(sections),
            "languages":      self._extract_languages(sections),
        }

    def _extract_pdf(self, file_bytes: bytes) -> str:
        if HAS_PYMUPDF:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                text = "\n".join(page.get_text("text") for page in doc)
                doc.close()
                if text.strip():
                    return self._clean_text(text)
            except Exception as e:
                logger.warning(f"PyMuPDF failed: {e}")
        return self._clean_text(file_bytes.decode("utf-8", errors="ignore"))

    def _extract_docx(self, file_bytes: bytes) -> str:
        if not HAS_DOCX:
            return file_bytes.decode("utf-8", errors="ignore")
        doc = DocxDocument(io.BytesIO(file_bytes))
        lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                if row_text:
                    lines.append(row_text)
        return self._clean_text("\n".join(lines))

    def _detect_sections(self, text: str) -> Dict[str, str]:
        lines = text.split("\n")
        sections: Dict[str, str] = {}
        current_section = "header"
        current_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_lines.append("")
                continue
            matched = self._match_section_header(stripped)
            if matched and len(stripped) < 60:
                if current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = matched
                current_lines = []
            else:
                current_lines.append(stripped)
        if current_lines:
            sections[current_section] = "\n".join(current_lines).strip()
        return sections

    def _match_section_header(self, line: str) -> Optional[str]:
        line_lower = line.lower()
        for section, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line_lower):
                    return section
        return None

    def _extract_contact_info(self, text: str) -> Dict:
        header = "\n".join(text.split("\n")[:30])
        return {
            "name":     self._extract_name(header),
            "email":    self._extract_email(header),
            "phone":    self._extract_phone(header),
            "linkedin": self._extract_linkedin(header),
            "github":   self._extract_github(header),
            "location": self._extract_location(header),
        }

    def _extract_name(self, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            c = lines[0]
            if 2 <= len(c.split()) <= 5 and "@" not in c and not re.search(r"\d", c) and len(c) < 50:
                return c
        return ""

    def _extract_email(self, text: str) -> str:
        m = re.findall(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
        return m[0] if m else ""

    def _extract_phone(self, text: str) -> str:
        m = re.findall(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        return m[0] if m else ""

    def _extract_linkedin(self, text: str) -> Optional[str]:
        m = re.search(r"linkedin\.com/in/([\w-]+)", text, re.IGNORECASE)
        return f"linkedin.com/in/{m.group(1)}" if m else None

    def _extract_github(self, text: str) -> Optional[str]:
        m = re.search(r"github\.com/([\w-]+)", text, re.IGNORECASE)
        return f"github.com/{m.group(1)}" if m else None

    def _extract_location(self, text: str) -> Optional[str]:
        m = re.search(r"\b([A-Z][a-zA-Z\s]+),\s*([A-Z]{2}|[A-Z][a-zA-Z\s]+)\b", "\n".join(text.split("\n")[:10]))
        return m.group(0) if m else None

    def _extract_summary(self, sections: Dict) -> Optional[str]:
        return sections.get("summary") or None

    def _extract_skills(self, sections: Dict, raw_text: str) -> List[str]:
        text = sections.get("skills", "") or raw_text
        raw = re.split(r"[,|•\n·]+", text)
        skills, seen = [], set()
        for s in raw:
            s = s.strip().strip("•-–—*").strip()
            if 2 <= len(s) <= 40 and not re.match(r"^\d+$", s) and s.lower() not in seen:
                seen.add(s.lower())
                skills.append(s)
        return skills[:80]

    def _extract_soft_skills(self, text: str) -> List[str]:
        SOFT = ["leadership","communication","teamwork","problem solving","critical thinking",
                "adaptability","creativity","time management","collaboration","analytical"]
        return [s.title() for s in SOFT if s in text.lower()]

    def _extract_experience(self, sections: Dict) -> List[Dict]:
        exp_text = sections.get("experience", "")
        if not exp_text:
            return []
        experiences = []
        date_pat = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[12]\d{3})[\s,–-]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[12]\d{3}|Present|Current)", re.IGNORECASE)
        for block in re.split(r"\n{2,}", exp_text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            entry = {"company":"","role":"","start_date":None,"end_date":None,"description":"","technologies":[]}
            desc = []
            for i, line in enumerate(lines):
                dm = date_pat.search(line)
                if dm and i < 4:
                    entry["start_date"] = dm.group(1)
                    entry["end_date"] = dm.group(2)
                elif i == 0:
                    entry["role"] = line
                elif i == 1 and not dm:
                    entry["company"] = line
                else:
                    desc.append(line)
            entry["description"] = "\n".join(desc)
            if entry["role"] or entry["company"]:
                experiences.append(entry)
        return experiences

    def _extract_education(self, sections: Dict) -> List[Dict]:
        edu_text = sections.get("education", "")
        if not edu_text:
            return []
        edus = []
        deg_pat = re.compile(r"\b(B\.?Tech|M\.?Tech|B\.?E|B\.?Sc|M\.?Sc|MBA|PhD|MCA|BCA|Bachelor|Master|Diploma)\b", re.IGNORECASE)
        for block in re.split(r"\n{2,}", edu_text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            entry = {"institution":"","degree":"","field":"","year":None,"gpa":None}
            for line in lines:
                dm = deg_pat.search(line)
                ym = re.search(r"\b(19|20)\d{2}\b", line)
                gm = re.search(r"(GPA|CGPA)[:\s]*([\d.]+)", line, re.IGNORECASE)
                if dm:
                    entry["degree"] = dm.group(0)
                    entry["field"] = line[dm.end():].strip("., :")[:60]
                elif ym and not entry["year"]:
                    entry["year"] = ym.group(0)
                elif gm:
                    entry["gpa"] = gm.group(2)
                elif not entry["institution"]:
                    entry["institution"] = line
            if entry["institution"] or entry["degree"]:
                edus.append(entry)
        return edus

    def _extract_projects(self, sections: Dict) -> List[Dict]:
        proj_text = sections.get("projects", "")
        if not proj_text:
            return []
        projects = []
        for block in re.split(r"\n{2,}", proj_text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            url_m = re.search(r"https?://[^\s]+|github\.com/[^\s]+", block, re.IGNORECASE)
            projects.append({
                "name": lines[0].strip("•-–—*:").strip(),
                "description": " ".join(lines[1:]),
                "technologies": [],
                "url": url_m.group(0) if url_m else None,
            })
        return projects

    def _extract_certifications(self, sections: Dict) -> List[str]:
        text = sections.get("certifications", "")
        if not text:
            return []
        return [l.strip("•-–—*:").strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]

    def _extract_languages(self, sections: Dict) -> List[str]:
        text = sections.get("languages", "")
        if not text:
            return []
        return [l.strip() for l in re.split(r"[,|•\n·]+", text) if l.strip()]

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()
