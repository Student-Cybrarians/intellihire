# ─────────────────────────────────────────────────────────
# IntelliHire — Module 1 Dockerfile
# Multi-stage build: builder → runtime
# ─────────────────────────────────────────────────────────

# Stage 1 — Builder: install all dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed for WeasyPrint, PyMuPDF, spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libffi-dev \
    libssl-dev \
    libglib2.0-0 \
    libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt

# Download spaCy language model
RUN /install/bin/python -m spacy download en_core_web_sm


# Stage 2 — Runtime: lean image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy app source
COPY . .

# Create runtime directories
RUN mkdir -p /app/uploads /app/reports

# Non-root user for security
RUN useradd -m -u 1001 intellihire && chown -R intellihire:intellihire /app
USER intellihire

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)"

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
