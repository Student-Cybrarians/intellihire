#!/bin/bash
# Azure App Service startup script
cd /home/site/wwwroot
pip install -r requirements.txt --quiet
python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True)" 2>/dev/null || true
uvicorn app.main:app --host 0.0.0.0 --port 8000
