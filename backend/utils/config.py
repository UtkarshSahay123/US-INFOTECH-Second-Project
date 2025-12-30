import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional

import pathlib


from dotenv import load_dotenv

# --- PATH RESOLUTION ---
# This finds the absolute path to your project root where the .env file lives
ROOT_DIR = pathlib.Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"

# Load the .env file explicitly from the root directory
load_dotenv(dotenv_path=ENV_PATH)


def _read_list(name: str, fallback: str | None = None) -> List[str]:
    raw = os.getenv(name, fallback or "")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "CardioSentinel API"))
    dataset_path: str = field(default_factory=lambda: os.getenv("DATASET_PATH", "data/heart_uci.csv"))
    model_path: str = field(default_factory=lambda: os.getenv("MODEL_PATH", "backend/ml/models/heart_attack_model.json"))
    stats_path: str = field(default_factory=lambda: os.getenv("STATS_PATH", "backend/ml/models/feature_stats.json"))
    report_path: str = field(default_factory=lambda: os.getenv("REPORT_PATH", "backend/ml/reports/training_report.json"))

    allowed_origins: List[str] = field(default_factory=lambda: _read_list("ALLOWED_ORIGINS", "*"))

    twilio_account_sid: Optional[str] = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID"))
    twilio_auth_token: Optional[str] = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN"))
    twilio_from_number: Optional[str] = field(default_factory=lambda: os.getenv("TWILIO_FROM_NUMBER"))

    emergency_primary_number: Optional[str] = field(default_factory=lambda: os.getenv("EMERGENCY_PRIMARY_NUMBER"))
    emergency_contacts: List[str] = field(default_factory=lambda: _read_list("EMERGENCY_CONTACTS"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
