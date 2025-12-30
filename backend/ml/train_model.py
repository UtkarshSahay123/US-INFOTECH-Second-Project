from __future__ import annotations

import csv
import json
import math
import pathlib
import random
from datetime import UTC, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from backend.utils.config import get_settings

FEATURE_ORDER = [
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
]


def sigmoid(value: float) -> float:
    capped = max(min(value, 60), -60)
    return 1.0 / (1.0 + math.exp(-capped))


def load_dataset(path: pathlib.Path) -> List[Dict[str, float]]:
    with path.open("r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        raw_rows: List[Dict[str, Optional[float]]] = []
        for row in reader:
            record: Dict[str, Optional[float]] = {}
            for feature in FEATURE_ORDER:
                value = row[feature].strip()
                record[feature] = float(value) if value != "?" else None
            target_val = row["target"].strip()
            record["target"] = 1.0 if float(target_val) >= 1 else 0.0
            raw_rows.append(record)

    feature_means: Dict[str, float] = {}
    for feature in FEATURE_ORDER:
        values = [entry[feature] for entry in raw_rows if entry[feature] is not None]
        feature_means[feature] = sum(values) / len(values)

    cleaned_rows: List[Dict[str, float]] = []
    for entry in raw_rows:
        cleaned = {}
        for feature in FEATURE_ORDER:
            value = entry[feature]
            cleaned[feature] = value if value is not None else feature_means[feature]
        cleaned["target"] = float(entry["target"])
        cleaned_rows.append(cleaned)
    return cleaned_rows


def compute_scaling(rows: Sequence[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    scaling: Dict[str, Dict[str, float]] = {}
    for feature in FEATURE_ORDER:
        values = [entry[feature] for entry in rows]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std = math.sqrt(variance) or 1.0
        scaling[feature] = {"mean": mean, "std": std}
    return scaling


def scale_row(row: Dict[str, float], scaling: Dict[str, Dict[str, float]]) -> List[float]:
    return [
        (row[feature] - scaling[feature]["mean"]) / scaling[feature]["std"]
        for feature in FEATURE_ORDER
    ]


def build_design_matrix(rows: Sequence[Dict[str, float]], scaling: Dict[str, Dict[str, float]]):
    X = [scale_row(row, scaling) for row in rows]
    y = [row["target"] for row in rows]
    return X, y


def train_logistic_regression(
    X: Sequence[List[float]],
    y: Sequence[float],
    epochs: int = 4500,
    lr: float = 0.045,
) -> Tuple[List[float], float]:
    feature_count = len(FEATURE_ORDER)
    weights = [0.0] * feature_count
    bias = 0.0
    sample_count = len(X)

    for epoch in range(epochs):
        grad_w = [0.0] * feature_count
        grad_b = 0.0
        for features, label in zip(X, y):
            score = sum(w * f for w, f in zip(weights, features)) + bias
            pred = sigmoid(score)
            diff = pred - label
            for idx in range(feature_count):
                grad_w[idx] += diff * features[idx]
            grad_b += diff
        step = lr / sample_count
        for idx in range(feature_count):
            weights[idx] -= step * grad_w[idx]
        bias -= step * grad_b
        if epoch % 750 == 0 and epoch:
            lr *= 0.9
    return weights, bias


def evaluate_model(weights: List[float], bias: float, X: Sequence[List[float]], y: Sequence[float]):
    predictions = []
    for features in X:
        score = sum(w * f for w, f in zip(weights, features)) + bias
        predictions.append(1 if sigmoid(score) >= 0.5 else 0)
    correct = sum(int(pred == label) for pred, label in zip(predictions, y))
    accuracy = correct / len(y)
    true_positive = sum(1 for pred, label in zip(predictions, y) if pred == 1 and label == 1)
    predicted_positive = sum(predictions)
    actual_positive = sum(1 for label in y if label == 1)
    precision = true_positive / predicted_positive if predicted_positive else 0.0
    recall = true_positive / actual_positive if actual_positive else 0.0
    return accuracy, precision, recall


def compute_feature_stats(rows: Sequence[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    def summarize(field: str):
        values = sorted(entry[field] for entry in rows)
        n = len(values)
        idx10 = max(int(0.10 * n) - 1, 0)
        idx90 = min(int(0.90 * n), n - 1)
        return {
            "mean": sum(values) / n,
            "p10": values[idx10],
            "p90": values[idx90],
            "min": values[0],
            "max": values[-1],
        }

    stats = {
        "bp_systolic": {**summarize("trestbps"), "healthy_low": 90.0, "healthy_high": 120.0},
        "cholesterol": {**summarize("chol"), "healthy_low": 125.0, "healthy_high": 200.0},
        "max_heart_rate": {**summarize("thalach"), "healthy_low": 90.0, "healthy_high": 170.0},
        "st_depression": {**summarize("oldpeak"), "healthy_low": 0.0, "healthy_high": 2.0},
    }
    stats["sugar_level"] = {
        "mean": 99.0,
        "p10": 70.0,
        "p90": 125.0,
        "min": 65.0,
        "max": 180.0,
        "healthy_low": 70.0,
        "healthy_high": 99.0,
    }
    stats["calories_burned"] = {
        "mean": 2000.0,
        "p10": 1200.0,
        "p90": 3500.0,
        "min": 800.0,
        "max": 4000.0,
        "healthy_low": 1500.0,
        "healthy_high": 3000.0,
    }
    return stats


def normalize_importance(weights: Sequence[float]) -> Dict[str, float]:
    raw = {feature: abs(weight) for feature, weight in zip(FEATURE_ORDER, weights)}
    total = sum(raw.values()) or 1.0
    return {feature: value / total for feature, value in raw.items()}


def persist_artifacts(
    model_payload: Dict[str, object],
    feature_stats: Dict[str, Dict[str, float]],
    report: Dict[str, object],
):
    settings = get_settings()
    model_path = pathlib.Path(settings.model_path)
    stats_path = pathlib.Path(settings.stats_path)
    report_path = pathlib.Path(settings.report_path)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with model_path.open("w", encoding="utf-8") as model_file:
        json.dump(model_payload, model_file, indent=2)
    with stats_path.open("w", encoding="utf-8") as stats_file:
        json.dump({"feature_stats": feature_stats}, stats_file, indent=2)
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2)


def main() -> None:
    settings = get_settings()
    data_path = pathlib.Path(settings.dataset_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found at {data_path}")

    rows = load_dataset(data_path)
    random.Random(42).shuffle(rows)
    scaling = compute_scaling(rows)
    X, y = build_design_matrix(rows, scaling)

    split_idx = int(0.8 * len(rows))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    weights, bias = train_logistic_regression(X_train, y_train)
    accuracy, precision, recall = evaluate_model(weights, bias, X_test, y_test)

    feature_stats = compute_feature_stats(rows)
    importance = normalize_importance(weights)

    model_payload = {
        "feature_order": FEATURE_ORDER,
        "weights": weights,
        "bias": bias,
        "scaling": scaling,
    }

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "samples": len(rows),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "feature_importance": importance,
    }

    persist_artifacts(model_payload, feature_stats, report)
    print("Training completed. Accuracy:", round(accuracy, 3))


if __name__ == "__main__":
    main()
