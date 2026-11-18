import os

PORT = int(os.environ.get("PORT", "8001"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_CONNECT_RETRIES = int(os.environ.get("DB_CONNECT_RETRIES", "10"))
APP_VERSION = os.environ.get("APP_VERSION", "dev")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8080").split(",")
    if origin.strip()
]
