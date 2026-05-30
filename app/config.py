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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
CANDIDATE_PROFILE_MODEL = os.getenv("CANDIDATE_PROFILE_MODEL", "gpt-5.4-mini")
VACANCY_ANALYZER_MODEL = os.getenv("VACANCY_ANALYZER_MODEL", "gpt-5.4-mini")
CAREER_STRATEGY_MODEL = os.getenv("CAREER_STRATEGY_MODEL", "gpt-5.4")
RESUME_WRITER_MODEL = os.getenv("RESUME_WRITER_MODEL", "gpt-5.4")
RESUME_CRITIC_MODEL = os.getenv("RESUME_CRITIC_MODEL", "gpt-5.4")
OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "false").lower() == "true" and bool(OPENAI_API_KEY)
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))

# CandidateProfile evidence experiment.
# false = keep LLM evidence as final evidence with soft cleanup only.
# true = validate LLM evidence against detected source blocks and use bounded fallback.
CANDIDATE_EVIDENCE_VALIDATION_ENABLED = os.getenv(
    "CANDIDATE_EVIDENCE_VALIDATION_ENABLED",
    "false",
).lower() == "true"

# Vacancy recommendation pool.
# On Railway this keeps the shared GetMatch vacancy pool populated without a
# manual one-off command after every deploy.
VACANCY_POOL_AUTO_SYNC = os.getenv("VACANCY_POOL_AUTO_SYNC", "true").lower() == "true"
VACANCY_POOL_MIN_SIZE = int(os.getenv("VACANCY_POOL_MIN_SIZE", "100"))
_vacancy_pool_limit = os.getenv("VACANCY_POOL_SYNC_LIMIT", "").strip()
VACANCY_POOL_SYNC_LIMIT = int(_vacancy_pool_limit) if _vacancy_pool_limit else None

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "exports")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Ensure directories exist
for dir_path in [UPLOADS_DIR, EXPORTS_DIR, DATA_DIR]:
    os.makedirs(dir_path, exist_ok=True)
