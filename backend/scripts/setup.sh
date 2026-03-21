#!/bin/bash
# scripts/setup.sh
# ─────────────────────────────────────────────────────────
# IntelliHire Module 1 — One-shot local setup
# Usage: chmod +x scripts/setup.sh && ./scripts/setup.sh
# ─────────────────────────────────────────────────────────

set -e   # exit on any error

PYTHON=${PYTHON:-python3}
VENV_DIR=".venv"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   IntelliHire — Module 1 Setup               ║"
echo "║   ATS Resume Analyzer & Generator            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Python version check ──────────────────────────
PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
REQUIRED="3.10"
if [[ "$(printf '%s\n' "$REQUIRED" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED" ]]; then
    echo "❌ Python $REQUIRED+ required. Found: $PYTHON_VERSION"
    exit 1
fi
echo "✅ Python $PYTHON_VERSION found"

# ── Step 2: Virtual environment ───────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment…"
    $PYTHON -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate
echo "✅ Virtual environment activated"

# ── Step 3: Install dependencies ──────────────────────────
echo "📥 Installing dependencies…"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

# ── Step 4: Download spaCy model ──────────────────────────
echo "🔤 Downloading spaCy model (en_core_web_sm)…"
python -m spacy download en_core_web_sm --quiet 2>/dev/null || echo "⚠️  spaCy model download failed — run manually: python -m spacy download en_core_web_sm"
echo "✅ spaCy model ready"

# ── Step 5: Create .env ───────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ .env created from .env.example"
    echo "⚠️  IMPORTANT: Edit .env and add your OPENAI_API_KEY or ANTHROPIC_API_KEY"
else
    echo "ℹ️  .env already exists — skipping"
fi

# ── Step 6: Create runtime directories ───────────────────
mkdir -p uploads reports
echo "✅ uploads/ and reports/ directories created"

# ── Step 7: Check MongoDB ────────────────────────────────
if command -v mongosh &> /dev/null; then
    if mongosh --eval "db.adminCommand('ping')" --quiet &>/dev/null; then
        echo "✅ MongoDB is running"
    else
        echo "⚠️  MongoDB not running — start it or use Docker: docker compose up -d mongodb"
    fi
else
    echo "ℹ️  mongosh not found — ensure MongoDB is running on localhost:27017"
    echo "   Quick start: docker compose up -d mongodb"
fi

# ── Done ─────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Setup Complete!                            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Edit .env — add your LLM API key"
echo "  2. Start MongoDB (if not running)"
echo "  3. Run the server:"
echo "     source .venv/bin/activate"
echo "     uvicorn app.main:app --reload"
echo ""
echo "  Or with Docker:"
echo "     docker compose up --build"
echo ""
echo "  API Docs: http://localhost:8000/docs"
echo "  Health:   http://localhost:8000/health"
echo ""
