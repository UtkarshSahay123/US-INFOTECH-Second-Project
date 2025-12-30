from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SexEnum(str, Enum):
    male = "male"
    female = "female"


class ChestPainEnum(str, Enum):
    typical = "typical_angina"
    atypical = "atypical_angina"
    non_anginal = "non_anginal"
    asymptomatic = "asymptomatic"


class RestECGEnum(str, Enum):
    normal = "normal"
    st_t_abnormality = "st_t_abnormality"
    hypertrophy = "left_ventricular_hypertrophy"


class SlopeEnum(str, Enum):
    up = "upsloping"
    flat = "flat"
    down = "downsloping"


class ThalEnum(str, Enum):
    normal = "normal"
    fixed_defect = "fixed_defect"
    reversible_defect = "reversible_defect"


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


@dataclass
class HealthPredictionRequest:
    name: str
    age: int
    sex: SexEnum
    chest_pain_type: ChestPainEnum
    bp_systolic: float
    bp_diastolic: float
    cholesterol: float
    sugar_level: float
    calories_burned: float
    max_heart_rate: float
    resting_ecg: RestECGEnum
    exercise_angina: bool
    st_depression: float
    slope: SlopeEnum
    num_major_vessels: int
    thalassemia: ThalEnum
    fasting_hours: float = 8.0
    smoker: bool = False
    diabetic: bool = False
    emergency_contacts: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "HealthPredictionRequest":
        required = [
            "name",
            "age",
            "sex",
            "chest_pain_type",
            "bp_systolic",
            "bp_diastolic",
            "cholesterol",
            "sugar_level",
            "calories_burned",
            "max_heart_rate",
            "resting_ecg",
            "exercise_angina",
            "st_depression",
            "slope",
            "num_major_vessels",
            "thalassemia",
        ]
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")

        return cls(
            name=str(data["name"]),
            age=int(data["age"]),
            sex=SexEnum(data["sex"]),
            chest_pain_type=ChestPainEnum(data["chest_pain_type"]),
            bp_systolic=float(data["bp_systolic"]),
            bp_diastolic=float(data["bp_diastolic"]),
            cholesterol=float(data["cholesterol"]),
            sugar_level=float(data["sugar_level"]),
            calories_burned=float(data["calories_burned"]),
            max_heart_rate=float(data["max_heart_rate"]),
            resting_ecg=RestECGEnum(data["resting_ecg"]),
            exercise_angina=_bool(data["exercise_angina"]),
            st_depression=float(data["st_depression"]),
            slope=SlopeEnum(data["slope"]),
            num_major_vessels=int(data["num_major_vessels"]),
            thalassemia=ThalEnum(data["thalassemia"]),
            fasting_hours=float(data.get("fasting_hours", 8)),
            smoker=_bool(data.get("smoker", False)),
            diabetic=_bool(data.get("diabetic", False)),
            emergency_contacts=_list(data.get("emergency_contacts")),
            notes=data.get("notes"),
        )


@dataclass
class HealthyRange:
    low: float
    high: float


@dataclass
class ChartDatum:
    label: str
    user_value: float
    recommended: HealthyRange
    population_avg: float


@dataclass
class HealthPredictionResponse:
    name: str
    risk_category: str
    risk_score: float
    probability: float
    classification: int
    advisory_message: str
    chart: List[ChartDatum]
    key_insights: List[str]
    feature_importance: Dict[str, float]
    recommended_actions: List[str]


@dataclass
class EmergencyRequest:
    reason: str
    vitals: Dict[str, str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contacts: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> "EmergencyRequest":
        if "reason" not in data or "vitals" not in data:
            raise ValueError("'reason' and 'vitals' are required")
        return cls(
            reason=str(data["reason"]),
            vitals={k: str(v) for k, v in data["vitals"].items()},
            latitude=float(data["latitude"]) if data.get("latitude") is not None else None,
            longitude=float(data["longitude"]) if data.get("longitude") is not None else None,
            contacts=_list(data.get("contacts")),
        )


@dataclass
class EmergencyResponse:
    sms_dispatched: List[str]
    calls_triggered: List[str]
    dry_run: bool = False
