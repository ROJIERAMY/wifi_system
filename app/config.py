import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'hotspot.db'}")
ADMIN_PASSWORD = os.environ.get("HOTSPOT_ADMIN_PASSWORD", "changeme")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-in-production")
