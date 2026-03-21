# IntelliHire — Module 1: ATS Resume Analyzer & Generator

> **B.Tech CSE (AI/ML) Major Project** — IntelliHire Platform  
> Domain: NLP + LLM + Computer Vision  
> Module 1 of 5

---

## Architecture Overview

```
POST /upload_resume          POST /analyze              POST /generate_resume
       │                            │                            │
       ▼                            ▼                            ▼
 ResumeParser              AnalysisService              ResumeGenerator
  ├─ PyMuPDF (PDF)          ├─ ATSScorer                 ├─ HTML Template
  ├─ pdfminer (fallback)    │   ├─ Keyword Match (30%)   ├─ WeasyPrint → PDF
  └─ python-docx (DOCX)     │   ├─ Skills Match (20%)    └─ ReportLab (fallback)
                             │   ├─ Exp Relevance (20%)
  Extracted Fields:          │   ├─ Formatting (10%)
  ├─ name, email, phone      │   ├─ Readability (10%)
  ├─ skills, soft_skills     │   └─ Section Complete(10%)
  ├─ experience              │
  ├─ education               └─ LLMService
  ├─ projects                    ├─ Improvement Suggestions
  └─ certifications              ├─ Bullet Enhancer
                                 └─ Summary Generator
       │                            │                            │
       ▼                            ▼                            ▼
  MongoDB (Beanie ODM)    ReportGenerator              MongoDB (result)
   resumes collection      ├─ JSON report
                           └─ PDF report (ReportLab)
```

---

## Folder Structure

```
intellihire/
├── app/
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           └── resume.py      # All 3 endpoints + download
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── database.py            # MongoDB init (Motor + Beanie)
│   │   └── exceptions.py          # Custom exception hierarchy
│   ├── models/                    # Beanie MongoDB documents
│   │   ├── resume.py              # ResumeDocument
│   │   └── analysis.py            # AnalysisDocument, JobDescriptionDocument
│   ├── schemas/
│   │   └── resume.py              # Pydantic v2 request/response schemas
│   ├── parsers/
│   │   └── resume_parser.py       # PDF + DOCX → structured dict
│   ├── services/
│   │   ├── ats_scorer.py          # 6-component ATS scorer
│   │   ├── llm_service.py         # OpenAI/Anthropic LLM calls
│   │   └── analysis_service.py    # Pipeline orchestrator
│   ├── generators/
│   │   └── resume_generator.py    # HTML + PDF resume generator
│   ├── reports/
│   │   └── report_generator.py    # JSON + PDF analysis reports
│   └── utils/
│       ├── text_utils.py          # Shared text helpers
│       └── file_utils.py          # File validation helpers
├── tests/
│   ├── test_parser.py             # Parser unit tests
│   ├── test_scorer.py             # ATS scorer unit tests
│   └── test_api.py                # API integration tests
├── scripts/
│   ├── setup.sh                   # One-shot local setup
│   └── mongo-init.js              # MongoDB collections + indexes
├── docs/
│   └── sample_requests.json       # All API request/response examples
├── Dockerfile                     # Multi-stage Docker build
├── docker-compose.yml             # API + MongoDB + Mongo Express
├── requirements.txt
├── .env.example
└── README.md
```

---

## ATS Scoring Logic

| Component | Weight | How Computed |
|---|---|---|
| **Keyword Match** | 30% | Regex word-boundary match: `(resume_keywords ∩ jd_keywords) / jd_keywords` |
| **Skills Match** | 20% | Exact + semantic similarity via `sentence-transformers` (cosine > 0.82 threshold) |
| **Experience Relevance** | 20% | Cosine similarity of experience text vs JD text using `all-MiniLM-L6-v2` |
| **Formatting** | 10% | Presence of: name, email, phone, LinkedIn, GitHub, ideal word count (300–800), bullets, dates |
| **Readability** | 10% | Flesch-Kincaid ease score (ideal 60–80 for professional text) |
| **Section Completeness** | 10% | `present_sections / expected_sections` (expected: skills, experience, education, projects, summary, certs) |

**Final ATS Score** = Σ(component_score × weight) × 100

---

## Quick Start

### Option A — Local

```bash
# 1. Clone and enter
git clone <your-repo> && cd intellihire

# 2. Run setup
chmod +x scripts/setup.sh && ./scripts/setup.sh

# 3. Add API key to .env
echo "OPENAI_API_KEY=sk-..." >> .env

# 4. Start MongoDB (if not running)
docker compose up -d mongodb

# 5. Run server
source .venv/bin/activate
uvicorn app.main:app --reload

# API Docs → http://localhost:8000/docs
```

### Option B — Docker (Full Stack)

```bash
cp .env.example .env
# Edit .env → add your API key

docker compose up --build
# API     → http://localhost:8000/docs
# Mongo UI → http://localhost:8081  (admin / intellihire123)
```

---

## API Usage Examples

### 1. Upload Resume

```bash
curl -X POST http://localhost:8000/api/v1/resume/upload_resume \
  -F "file=@/path/to/john_doe_resume.pdf"
```

```json
{
  "resume_id": "64b3a1f0c9d4e2001f3a9b12",
  "message": "Resume parsed successfully",
  "word_count": 412,
  "sections_detected": ["skills", "experience", "education", "projects"]
}
```

### 2. Analyse vs Job Description

```bash
curl -X POST http://localhost:8000/api/v1/resume/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_id": "64b3a1f0c9d4e2001f3a9b12",
    "job_description": "We need a Senior Python/FastAPI engineer with Docker, Kubernetes, AWS experience...",
    "job_title": "Senior Software Engineer",
    "enhance_bullets": true
  }'
```

```json
{
  "ats_score": 76.4,
  "match_percentage": 81.2,
  "missing_skills": ["Kubernetes", "LangChain", "Machine Learning"],
  "improvement_suggestions": [
    "Add a professional summary targeting the Senior Software Engineer role",
    "Include 'Kubernetes' explicitly in your experience section"
  ],
  "enhanced_bullets": [
    {
      "original": "Built REST APIs using FastAPI reducing response time by 35%",
      "enhanced": "Architected 5 FastAPI REST APIs reducing average latency by 35%, serving 50k daily users"
    }
  ]
}
```

### 3. Generate ATS-Friendly Resume

```bash
curl -X POST http://localhost:8000/api/v1/resume/generate_resume \
  -H "Content-Type: application/json" \
  -d '{
    "resume_id": "64b3a1f0c9d4e2001f3a9b12",
    "analysis_id": "64b3c2f0d9e5f3001a4b8c45",
    "target_job_title": "Senior Software Engineer",
    "template": "modern"
  }'
```

```json
{
  "download_url": "/api/v1/resume/download/John_Doe_a1b2c3.pdf",
  "template_used": "modern"
}
```

---

## MongoDB Schema

### `resumes` collection
```json
{
  "_id": "ObjectId",
  "name": "string",
  "email": "string",
  "phone": "string",
  "linkedin": "string | null",
  "github": "string | null",
  "location": "string | null",
  "skills": ["string"],
  "soft_skills": ["string"],
  "experience": [{ "role": "", "company": "", "start_date": "", "description": "" }],
  "education": [{ "degree": "", "institution": "", "year": "", "gpa": "" }],
  "projects": [{ "name": "", "description": "", "technologies": [] }],
  "certifications": ["string"],
  "section_flags": { "skills": true, "experience": true, "education": true },
  "word_count": 412,
  "raw_text": "string",
  "uploaded_at": "ISODate"
}
```

### `analyses` collection
```json
{
  "_id": "ObjectId",
  "resume_id": "string",
  "jd_id": "string",
  "ats_score": 76.4,
  "match_percentage": 81.2,
  "score_breakdown": [{ "component": "", "raw_score": 0.0, "weighted_score": 0.0, "weight": 0.0 }],
  "matched_keywords": ["string"],
  "missing_keywords": ["string"],
  "missing_skills": ["string"],
  "improvement_suggestions": ["string"],
  "enhanced_bullets": [{ "original": "", "enhanced": "" }],
  "report_pdf_path": "string",
  "analyzed_at": "ISODate"
}
```

---

## Run Tests

```bash
source .venv/bin/activate
pytest tests/ -v --tb=short
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.111 + Uvicorn |
| NLP | spaCy 3.7 (en_core_web_lg) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| PDF Parsing | PyMuPDF + pdfminer.six |
| DOCX Parsing | python-docx |
| LLM | OpenAI GPT-4o / Anthropic Claude 3.5 |
| Database | MongoDB 7.0 + Motor (async) + Beanie (ODM) |
| PDF Generation | WeasyPrint + ReportLab (fallback) |
| Readability | textstat (Flesch-Kincaid) |
| Retry Logic | tenacity |
| Testing | pytest + httpx |
| Deployment | Docker + docker-compose |

---

## Part of IntelliHire Platform

| Module | Description | Status |
|---|---|---|
| **M1** | ATS Resume Analyzer & Generator | ✅ This repo |
| M2 | Aptitude Round — Adaptive MCQ + Voice | 🔜 |
| M3 | Technical Round — DSA + LLM Voice | 🔜 |
| M4 | HR Round Simulator — NLP Sentiment | 🔜 |
| M5 | CV Behavioral Analysis — Face/Eye/Emotion | 🔜 |
