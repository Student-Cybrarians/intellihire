"""
app/generators/resume_generator.py
────────────────────────────────────
ATS-friendly resume generator.

Produces:
  1. Clean HTML (Jinja2 template rendered)
  2. ATS-optimised PDF (via WeasyPrint HTML→PDF)
  3. Falls back to ReportLab if WeasyPrint unavailable

ATS rules followed:
  - Standard section headings (not creative labels)
  - No tables, columns, or text boxes (ATS parsers hate these)
  - Machine-readable fonts (no custom/fancy fonts)
  - Proper heading hierarchy
  - Contact info at top, plaintext
"""

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# HTML Template (ATS-safe, single-column, no tables)
# ─────────────────────────────────────────────────────────

ATS_RESUME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} - Resume</title>
<style>
  /* ATS-SAFE CSS: minimal, no flexbox/grid for layout */
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 11pt;
    line-height: 1.4;
    color: #111;
    max-width: 780px;
    margin: 0 auto;
    padding: 30px 40px;
  }}
  h1 {{ font-size: 20pt; margin-bottom: 4px; }}
  .contact {{ font-size: 10pt; color: #333; margin-bottom: 16px; }}
  .contact span {{ margin-right: 16px; }}
  h2 {{
    font-size: 12pt;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1.5px solid #333;
    padding-bottom: 3px;
    margin: 16px 0 8px;
  }}
  .summary {{ margin-bottom: 8px; }}
  .entry {{ margin-bottom: 12px; }}
  .entry-header {{ font-weight: bold; font-size: 11pt; }}
  .entry-sub {{ font-size: 10pt; color: #444; margin-bottom: 4px; }}
  ul {{ padding-left: 18px; margin: 4px 0; }}
  li {{ margin-bottom: 3px; }}
  .skills-list {{ line-height: 1.8; }}
  .section {{ margin-bottom: 6px; }}
  @media print {{
    body {{ padding: 20px 30px; }}
    h2 {{ page-break-after: avoid; }}
    .entry {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>

<!-- HEADER -->
<h1>{name}</h1>
<div class="contact">
  {email_span}{phone_span}{linkedin_span}{github_span}{location_span}
</div>

{summary_section}

<!-- SKILLS -->
{skills_section}

<!-- EXPERIENCE -->
{experience_section}

<!-- EDUCATION -->
{education_section}

<!-- PROJECTS -->
{projects_section}

<!-- CERTIFICATIONS -->
{certifications_section}

</body>
</html>"""


class ResumeGenerator:
    """
    Generates ATS-friendly resumes as HTML and PDF.

    Usage:
        gen = ResumeGenerator()
        result = await gen.generate(user_data, template="modern")
    """

    async def generate(self, user_data: Dict, template: str = "modern") -> Dict:
        """
        Main entry point.

        Args:
            user_data: merged dict of parsed resume + any user overrides
            template: currently "modern" | "minimal" (same structure, minor style diff)

        Returns:
            {html_content, pdf_path, download_url}
        """
        html = self._render_html(user_data)
        pdf_path = await self._render_pdf(html, user_data.get("name", "resume"))
        download_url = f"/download/resume/{pdf_path.name}"

        return {
            "html_content": html,
            "pdf_path": str(pdf_path),
            "download_url": download_url,
        }

    # ──────────────────────────────────────────────────────
    # HTML rendering
    # ──────────────────────────────────────────────────────

    def _render_html(self, data: Dict) -> str:
        """Build ATS-safe HTML from resume data."""

        # Contact spans
        def span(val: Optional[str], label: str = "") -> str:
            if not val:
                return ""
            return f'<span>{label}{val}</span>'

        email_span    = span(data.get("email"), "✉ ")
        phone_span    = span(data.get("phone"), "📞 ")
        linkedin_span = span(data.get("linkedin"), "🔗 ")
        github_span   = span(data.get("github"), "⌨ ")
        location_span = span(data.get("location"))

        # Summary
        summary_section = ""
        if data.get("summary"):
            summary_section = f"""<h2>Professional Summary</h2>
<div class="summary">{data['summary']}</div>"""

        # Skills
        skills_section = ""
        if data.get("skills"):
            skills_str = " • ".join(data["skills"][:40])
            skills_section = f"""<h2>Skills</h2>
<div class="skills-list">{skills_str}</div>"""

        # Experience
        experience_section = self._render_experience(data.get("experience", []))

        # Education
        education_section = self._render_education(data.get("education", []))

        # Projects
        projects_section = self._render_projects(data.get("projects", []))

        # Certifications
        certifications_section = ""
        certs = data.get("certifications", [])
        if certs:
            cert_items = "\n".join(f"<li>{c}</li>" for c in certs)
            certifications_section = f"""<h2>Certifications</h2>
<ul>{cert_items}</ul>"""

        return ATS_RESUME_HTML.format(
            name=data.get("name", "Your Name"),
            email_span=email_span,
            phone_span=phone_span,
            linkedin_span=linkedin_span,
            github_span=github_span,
            location_span=location_span,
            summary_section=summary_section,
            skills_section=skills_section,
            experience_section=experience_section,
            education_section=education_section,
            projects_section=projects_section,
            certifications_section=certifications_section,
        )

    def _render_experience(self, experiences: List[Dict]) -> str:
        if not experiences:
            return ""

        items = []
        for exp in experiences:
            role      = exp.get("role", "")
            company   = exp.get("company", "")
            start     = exp.get("start_date", "")
            end       = exp.get("end_date", "Present")
            date_str  = f"{start} – {end}" if start else ""

            # Use enhanced bullets if available, else raw description
            bullets = []
            if exp.get("enhanced_bullets"):
                bullets = [b["enhanced"] for b in exp["enhanced_bullets"]]
            elif exp.get("description"):
                bullets = [
                    l.strip().lstrip("•-–*").strip()
                    for l in exp["description"].split("\n")
                    if l.strip()
                ]

            bullet_html = ""
            if bullets:
                bullet_html = "<ul>" + "\n".join(f"<li>{b}</li>" for b in bullets[:8]) + "</ul>"

            items.append(f"""<div class="entry">
  <div class="entry-header">{role} — {company}</div>
  <div class="entry-sub">{date_str}</div>
  {bullet_html}
</div>""")

        return f"<h2>Work Experience</h2>\n" + "\n".join(items)

    def _render_education(self, educations: List[Dict]) -> str:
        if not educations:
            return ""

        items = []
        for edu in educations:
            degree = edu.get("degree", "")
            field  = edu.get("field", "")
            inst   = edu.get("institution", "")
            year   = edu.get("year", "")
            gpa    = edu.get("gpa", "")
            gpa_str = f" | GPA: {gpa}" if gpa else ""

            items.append(f"""<div class="entry">
  <div class="entry-header">{degree} in {field}</div>
  <div class="entry-sub">{inst} | {year}{gpa_str}</div>
</div>""")

        return "<h2>Education</h2>\n" + "\n".join(items)

    def _render_projects(self, projects: List[Dict]) -> str:
        if not projects:
            return ""

        items = []
        for proj in projects:
            name = proj.get("name", "")
            desc = proj.get("description", "")
            tech = proj.get("technologies", [])
            url  = proj.get("url", "")
            tech_str = f" | Tech: {', '.join(tech)}" if tech else ""
            url_str  = f" | <a href='{url}'>{url}</a>" if url else ""

            items.append(f"""<div class="entry">
  <div class="entry-header">{name}{url_str}</div>
  <div class="entry-sub">{tech_str}</div>
  <p>{desc}</p>
</div>""")

        return "<h2>Projects</h2>\n" + "\n".join(items)

    # ──────────────────────────────────────────────────────
    # PDF rendering
    # ──────────────────────────────────────────────────────

    async def _render_pdf(self, html: str, name: str) -> Path:
        """
        Convert HTML to PDF.
        Tries WeasyPrint first (best CSS support), falls back to ReportLab.
        """
        safe_name = re.sub(r"[^\w]", "_", name)
        filename  = f"{safe_name}_{uuid.uuid4().hex[:8]}.pdf"
        out_path  = settings.REPORTS_DIR / filename

        # Try WeasyPrint
        try:
            from weasyprint import HTML as WeasyHTML
            WeasyHTML(string=html).write_pdf(str(out_path))
            logger.info(f"PDF generated via WeasyPrint: {out_path}")
            return out_path
        except ImportError:
            logger.warning("WeasyPrint not available, falling back to ReportLab")
        except Exception as e:
            logger.warning(f"WeasyPrint failed: {e}. Falling back to ReportLab.")

        # Fallback: ReportLab
        return self._reportlab_fallback(html, out_path, name)

    def _reportlab_fallback(self, html: str, out_path: Path, candidate_name: str) -> Path:
        """
        Minimal ReportLab PDF — used when WeasyPrint is unavailable.
        Strips HTML and formats as structured text.
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer
        )

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )

        styles = getSampleStyleSheet()
        name_style  = ParagraphStyle("Name",  parent=styles["h1"], fontSize=18, spaceAfter=4)
        h2_style    = ParagraphStyle("H2",    parent=styles["h2"], fontSize=12, spaceAfter=4,
                                     spaceBefore=10, textColor=colors.HexColor("#222"))
        body_style  = ParagraphStyle("Body",  parent=styles["Normal"], fontSize=10, spaceAfter=2)
        bold_style  = ParagraphStyle("Bold",  parent=styles["Normal"], fontSize=10,
                                     fontName="Helvetica-Bold", spaceAfter=2)

        # Strip HTML for text
        clean = re.compile(r"<[^>]+>")
        raw   = clean.sub(" ", html)
        raw   = re.sub(r"\s+", " ", raw).strip()

        story = [
            Paragraph(candidate_name, name_style),
            Spacer(1, 6),
            Paragraph(f"Generated by IntelliHire on {datetime.utcnow().strftime('%Y-%m-%d')}", body_style),
            Spacer(1, 6),
            HRFlowable(width="100%", thickness=1),
            Spacer(1, 6),
            Paragraph(raw[:3000], body_style),   # simplified: dump cleaned text
        ]

        doc.build(story)
        logger.info(f"PDF generated via ReportLab fallback: {out_path}")
        return out_path
