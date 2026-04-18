"""
Production ADK Agent Server
Run: uvicorn main:app --host 0.0.0.0 --port 8080
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from google.adk.cli.fast_api import get_fast_api_app

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=os.environ.get(
        "SESSION_SERVICE_URI",
        "sqlite+aiosqlite:///./sessions.db"
    ),
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    web=os.environ.get("SERVE_WEB_UI", "false").lower() == "true",
)
