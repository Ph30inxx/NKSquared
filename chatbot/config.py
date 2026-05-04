import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────────────────────────
# Reuse the same DATABASE_URL the platform backend uses.
# Format from .env: postgresql+psycopg://user:pass@host:port/db
_raw_db_url = os.getenv("DATABASE_URL", "postgresql+psycopg://nksquared_user:dev@postgres:5432/nksquared")

# Agno's PostgresAgentStorage and our psycopg2 tools need the plain URL.
# Strip the driver suffix to get a psycopg2-compatible URL.
DB_URL_SYNC = _raw_db_url.replace("postgresql+psycopg://", "postgresql://")

# Agno internally uses psycopg2 for storage; pass the sync URL everywhere.
DB_URL = DB_URL_SYNC

# ── Azure OpenAI ──────────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT   = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# ── Agent settings ────────────────────────────────────────────────────────────
AGENT_SESSION_TABLE     = "agent_sessions"
AGENT_NUM_HISTORY_RUNS  = 6

# ── Query safety ──────────────────────────────────────────────────────────────
SAFE_QUERY_ROW_LIMIT = 500

# ── Auth (same SECRET_KEY as platform backend) ────────────────────────────────
JWT_SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM  = "HS256"

# ── Fiscal year ───────────────────────────────────────────────────────────────
FY_START_MONTH = 4      # April — Indian financial year
