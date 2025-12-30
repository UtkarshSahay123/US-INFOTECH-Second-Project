from __future__ import annotations

import logging
import pathlib
from dataclasses import asdict

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.api.schemas import EmergencyRequest, EmergencyResponse, HealthPredictionRequest
from backend.ml.predictor import HeartAttackPredictor
from backend.services.emergency import EmergencyDispatcher
from backend.utils.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
frontend_path = pathlib.Path("frontend").resolve()

app = Flask(__name__, static_folder=str(frontend_path), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": settings.allowed_origins or ["*"]}})

predictor = HeartAttackPredictor()
emergency_dispatcher = EmergencyDispatcher()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "model": "loaded" if predictor.weights else "loading"})


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True, silent=False) or {}
    try:
        payload = HealthPredictionRequest.from_dict(data)
        result = predictor.predict(payload)
        return jsonify(asdict(result))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        logger.exception("Model artifacts missing")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/emergency/notify", methods=["POST"])
def emergency_notify():
    data = request.get_json(force=True, silent=False) or {}
    try:
        payload = EmergencyRequest.from_dict(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    sms_contacts = emergency_dispatcher.send_sms_alert(
        reason=payload.reason,
        vitals=payload.vitals,
        latitude=payload.latitude,
        longitude=payload.longitude,
        contacts=payload.contacts,
    )
    call_contacts = emergency_dispatcher.place_phone_call(
        voice_message=payload.reason,
        latitude=payload.latitude,
        longitude=payload.longitude,
        contacts=payload.contacts,
    )
    response = EmergencyResponse(
        sms_dispatched=sms_contacts,
        calls_triggered=call_contacts,
        dry_run=not emergency_dispatcher.is_configured,
    )
    return jsonify(asdict(response))


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    if not frontend_path.exists():
        return jsonify({"message": "API running"})
    full_path = frontend_path / path
    if path and full_path.exists() and full_path.is_file():
        return send_from_directory(frontend_path, path)
    return send_from_directory(frontend_path, "index.html")
