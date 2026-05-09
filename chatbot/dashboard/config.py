import os

from chatbot.config import (
    DB_URL_SYNC,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    FY_START_MONTH,
    SAFE_QUERY_ROW_LIMIT,
)

DASHBOARD_STORAGE_PATH = os.getenv(
    "DASHBOARD_STORAGE_PATH",
    os.path.join(os.path.dirname(__file__), "storage"),
)

os.makedirs(DASHBOARD_STORAGE_PATH, exist_ok=True)
