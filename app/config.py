import os
from dotenv import load_dotenv

load_dotenv()

# Application
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")
OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "false").lower() == "true" and bool(OPENAI_API_KEY)
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "exports")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Ensure directories exist
for dir_path in [UPLOADS_DIR, EXPORTS_DIR, DATA_DIR]:
    os.makedirs(dir_path, exist_ok=True)
