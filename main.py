"""
Root-level entry point for Render.
Adds backend/ to Python path so imports work correctly.
"""
import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import the FastAPI app from backend
from app.main import app  # noqa: F401
