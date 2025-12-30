from __future__ import annotations

import json
import math
import pathlib
from typing import Dict, List

from backend.api.schemas import ChartDatum, HealthPredictionRequest, HealthPredictionResponse, HealthyRange
from backend.utils.config import get_settings

CHEST_PAIN_MAPPING = {
    "typical_angina": 1,
    "atypical_angina": 2,
    "non_anginal": 3,
    "asymptomatic": 4,
}
REST_ECG_MAPPING = {
    "normal": 0,
    "st_t_abnormality": 1,
    "left_ventricular_hypertrophy": 2,
}
SLOPE_MAPPING = {
    "upsloping": 1,
    "flat": 2,
    "downsloping": 3,
}
THAL_MAPPING = {
    "normal": 3,
    "fixed_defect": 6,
    "reversible_defect": 7,
}


class HeartAttackPredictor:
    def __init__(self) -> None:
        settings = get_settings()
        self.model_path = pathlib.Path(settings.model_path)
        self.stats_path = pathlib.Path(settings.stats_path)
        self.report_path = pathlib.Path(settings.report_path)
        self.feature_order: List[str] = []
        self.weights: List[float] = []
        self.bias: float = 0.0
        self.scaling: Dict[str, Dict[str, float]] = {}
        self._stats: Dict[str, Dict[str, float]] = {}
        self._feature_importance: Dict[str, float] = {}
        self.load_artifacts()

    def load_artifacts(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model artifact missing at {self.model_path}")
        if not self.stats_path.exists():
            raise FileNotFoundError(f"Feature stats missing at {self.stats_path}")

        with self.model_path.open("r", encoding="utf-8") as model_file:
            payload = json.load(model_file)
            self.feature_order = payload["feature_order"]
            self.weights = payload["weights"]
            self.bias = payload["bias"]
            self.scaling = payload["scaling"]

        with self.stats_path.open("r", encoding="utf-8") as stats_file:
            stats_payload = json.load(stats_file)
            self._stats = stats_payload.get("feature_stats", stats_payload)

        if self.report_path.exists():
            with self.report_path.open("r", encoding="utf-8") as report_file:
                report_payload = json.load(report_file)
                self._feature_importance = report_payload.get("feature_importance", {})
        else:
            self._feature_importance = {}

    def _request_vector(self, payload: HealthPredictionRequest) -> List[float]:
        row = {
            "age": float(payload.age),
            "sex": 1.0 if payload.sex.value == "male" else 0.0,
            "cp": float(CHEST_PAIN_MAPPING[payload.chest_pain_type.value]),
            "trestbps": float(payload.bp_systolic),
            "chol": float(payload.cholesterol),
            "fbs": 1.0 if payload.sugar_level >= 126 else 0.0,
            "restecg": float(REST_ECG_MAPPING[payload.resting_ecg.value]),
            "thalach": float(payload.max_heart_rate),
            "exang": 1.0 if payload.exercise_angina else 0.0,
            "oldpeak": float(payload.st_depression),
            "slope": float(SLOPE_MAPPING[payload.slope.value]),
            "ca": float(payload.num_major_vessels),
            "thal": float(THAL_MAPPING[payload.thalassemia.value]),
        }
        vector: List[float] = []
        for feature in self.feature_order:
            stats = self.scaling.get(feature)
            value = row[feature]
            if stats:
                value = (value - stats["mean"]) / stats["std"]
            vector.append(value)
        return vector

    def _predict_probability(self, vector: List[float]) -> float:
        score = sum(weight * value for weight, value in zip(self.weights, vector)) + self.bias
        capped = max(min(score, 60), -60)
        return 1.0 / (1.0 + math.exp(-capped))

    @staticmethod
    def _categorize_risk(probability: float) -> str:
        if probability < 0.33:
            return "Low"
        if probability < 0.66:
            return "Moderate"
        return "High"

    def _chart_data(self, payload: HealthPredictionRequest) -> List[ChartDatum]:
        chart_fields = [
            ("bp_systolic", payload.bp_systolic),
            ("cholesterol", payload.cholesterol),
            ("max_heart_rate", payload.max_heart_rate),
            ("sugar_level", payload.sugar_level),
        ]
        chart: List[ChartDatum] = []
        for field, value in chart_fields:
            stats = self._stats.get(field)
            if not stats:
                continue
            chart.append(
                ChartDatum(
                    label=field.replace("_", " ").title(),
                    user_value=float(value),
                    recommended=HealthyRange(low=stats["healthy_low"], high=stats["healthy_high"]),
                    population_avg=stats["mean"],
                )
            )
        return chart

    def _insights(self, payload: HealthPredictionRequest) -> List[str]:
        insights: List[str] = []
        bp_stats = self._stats.get("bp_systolic", {})
        if bp_stats and payload.bp_systolic > bp_stats.get("p90", payload.bp_systolic + 1):
            insights.append(
                "Blood pressure is above the 90th percentile of the dataset, indicating excess arterial strain."
            )
        chol_stats = self._stats.get("cholesterol", {})
        if chol_stats and payload.cholesterol > chol_stats.get("p90", payload.cholesterol + 1):
            insights.append("Cholesterol is significantly elevated compared to peers in the dataset.")
        if payload.exercise_angina:
            insights.append("Exercise-induced angina reported; schedule a stress test at the earliest.")
        if payload.sugar_level >= 126:
            insights.append("Fasting sugar indicates possible diabetes; coordinate with an endocrinologist.")
        if payload.calories_burned < self._stats.get("calories_burned", {}).get("healthy_low", 1500):
            insights.append("Weekly calorie burn is below the recommended range; integrate moderate activity.")
        if not insights:
            insights.append("Vitals fall inside the population averages; maintain the current lifestyle and monitoring cadence.")
        return insights

    def _recommendations(self, risk_category: str, payload: HealthPredictionRequest) -> List[str]:
        recommendations = [
            "Log BP, sugar, and symptoms daily to capture subtle drifts.",
            "Share this summary with your cardiologist for medication alignment.",
        ]
        if risk_category != "Low":
            recommendations.append("Book a complete lipid profile and stress ECG within the next 7 days.")
            recommendations.append("Keep sublingual nitrate handy and avoid strenuous workouts until cleared.")
        if payload.calories_burned < 1500:
            recommendations.append("Walk 30 minutes/day or follow physician-approved cardio rehab plan.")
        if payload.sugar_level >= 126:
            recommendations.append("Bring fasting sugar under 110 mg/dL through diet, metformin, or both.")
        return recommendations

    def predict(self, payload: HealthPredictionRequest) -> HealthPredictionResponse:
        if not self.weights:
            raise RuntimeError("Model weights missing")

        vector = self._request_vector(payload)
        probability = self._predict_probability(vector)
        classification = 1 if probability >= 0.5 else 0
        risk_category = self._categorize_risk(probability)
        risk_score = round(probability * 100, 2)

        advisory = (
            "High myocardial infarction risk detected." if risk_category == "High" else "Risk is manageable with standard precautions."
        )

        chart = self._chart_data(payload)
        insights = self._insights(payload)
        recommendations = self._recommendations(risk_category, payload)

        return HealthPredictionResponse(
            name=payload.name,
            risk_category=risk_category,
            risk_score=risk_score,
            probability=probability,
            classification=classification,
            advisory_message=advisory,
            chart=chart,
            key_insights=insights,
            feature_importance=self._feature_importance,
            recommended_actions=recommendations,
        )
