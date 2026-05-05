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
AGENT_NUM_HISTORY_RUNS  = 4

# ── Query safety ──────────────────────────────────────────────────────────────
SAFE_QUERY_ROW_LIMIT = 500

# ── Auth (same SECRET_KEY as platform backend) ────────────────────────────────
JWT_SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM  = "HS256"

# ── Voice / Vapi ─────────────────────────────────────────────────────────────
REDIS_URL               = os.getenv("REDIS_URL", "redis://redis:6379/0")
VAPI_SHARED_SECRET      = os.getenv("VAPI_SHARED_SECRET", "")
VAPI_ASSISTANT_ID       = os.getenv("VAPI_ASSISTANT_ID", "")
VOICE_COMPRESSOR_DEPLOYMENT  = os.getenv("VOICE_COMPRESSOR_DEPLOYMENT", "gpt-4o-mini")
VOICE_COMPRESSOR_API_VERSION = os.getenv("VOICE_COMPRESSOR_API_VERSION", AZURE_OPENAI_API_VERSION)
# Dev only — disable x-vapi-secret check for curl/Postman testing. Never True in prod.
VAPI_SERVER_AUTH_DISABLED = os.getenv("VAPI_SERVER_AUTH_DISABLED", "false").lower() == "true"

# ── Backend API (write operations) ───────────────────────────────────────────
# Write tools call the existing FastAPI backend over HTTP, forwarding the
# analyst's JWT token so all business logic, MOIC recomputation, and audit
# logging runs through the normal backend service layer.
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://api:8000/api/v1")

# ── Fiscal year ───────────────────────────────────────────────────────────────
FY_START_MONTH = 4      # April — Indian financial year
