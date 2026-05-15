"""Production-ready configuration management for SchoolSnap AI"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Security & Auth ──────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "schoolsnap-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "30"))

# Warn if using default SECRET_KEY in production
if SECRET_KEY == "schoolsnap-secret-key-change-in-production":
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise ValueError("⚠️ CRITICAL: Using default SECRET_KEY in production! Set SECRET_KEY env var.")

# ─── AI & Matching Thresholds ─────────────────────────────────────────
STRICT_MATCH_THRESHOLD = float(os.getenv("STRICT_MATCH_THRESHOLD", "0.55"))
MAX_MATCH_RESULTS = int(os.getenv("MAX_MATCH_RESULTS", "20"))
DATASET_MAX_DISTANCE = float(os.getenv("DATASET_MAX_DISTANCE", "0.9"))
DATASET_TOP_K = int(os.getenv("DATASET_TOP_K", "12"))
PARENT_FACE_ACCEPT_DISTANCE = float(os.getenv("PARENT_FACE_ACCEPT_DISTANCE", "0.82"))

# ─── Demo Credentials ─────────────────────────────────────────────────
DEMO_DATASET_EMAIL = os.getenv("DEMO_DATASET_EMAIL", "dataset-admin@demo.local")
DEMO_DATASET_PASSWORD = os.getenv("DEMO_DATASET_PASSWORD", "demo123")
DEMO_DATASET_NAME = os.getenv("DEMO_DATASET_NAME", "Dataset Admin")

# ─── Environment & Debugging ──────────────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
MAX_FILE_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ─── CORS Configuration ───────────────────────────────────────────────
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# ─── Rate Limiting ────────────────────────────────────────────────────
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# ─── Logging Configuration ────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─── File Paths ───────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "images", "events")
PREVIEW_DIR = os.path.join(BASE_DIR, "images", "previews")
SELFIES_DIR = os.path.join(BASE_DIR, "images", "selfies")
EVENT_UPLOAD_DIR = os.path.join(BASE_DIR, "event_uploads_tmp")

# Create directories if they don't exist
for directory in [UPLOAD_DIR, PREVIEW_DIR, SELFIES_DIR, EVENT_UPLOAD_DIR]:
    os.makedirs(directory, exist_ok=True)

# ─── Demo Accounts ────────────────────────────────────────────────────
DEMO_PARENT_ACCOUNTS = [
    {
        "registration_number": "REG1001",
        "dob": "2014-05-12",
        "parent_name": "Ravi Kumar",
        "child_name": "Aarav Kumar",
    },
    {
        "registration_number": "REG1002",
        "dob": "2013-09-22",
        "parent_name": "Sneha Reddy",
        "child_name": "Isha Reddy",
    },
    {
        "registration_number": "REG1003",
        "dob": "2015-01-18",
        "parent_name": "Vikram Rao",
        "child_name": "Vihaan Rao",
    },
]

logger.info(f"🚀 SchoolSnap AI initialized - Environment: {ENVIRONMENT}")
