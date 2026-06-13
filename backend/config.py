"""
config.py
All environment variables, model settings, path constants, and logging setup.
Imported by every other module — never imports from sibling modules.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RESEND_API_KEY     = os.getenv("RESEND_API_KEY", "")

# ── LLM ───────────────────────────────────────────────────────────────────────
DEFAULT_MODEL   = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS  = 1024

# ── Storage ───────────────────────────────────────────────────────────────────
AUDIT_LOG_PATH  = Path("crm_audit_log.jsonl")
SENT_EMAILS_LOG = Path("crm_sent_emails.jsonl")
EXPORT_DIR      = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

# ── Query limits ──────────────────────────────────────────────────────────────
DEFAULT_QUERY_LIMIT = 500
MAX_QUERY_LIMIT     = 5000

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ai_crm")

if not GROQ_API_KEY:
    logger.warning(" GROQ_API_KEY not set. LLM features will fail.")
else:
    logger.info("GROQ_API_KEY loaded.")
