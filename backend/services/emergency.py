from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from backend.utils.config import get_settings

logger = logging.getLogger(__name__)


def _format_location_link(latitude: Optional[float], longitude: Optional[float]) -> str:
    if latitude is None or longitude is None:
        return "Location unavailable"
    return f"https://www.google.com/maps?q={latitude},{longitude}"


class EmergencyDispatcher:
    """Handles SMS and voice call escalations via Twilio."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = self._create_client()

    def _create_client(self) -> Optional[Client]:
        if (
            self.settings.twilio_account_sid
            and self.settings.twilio_auth_token
            and self.settings.twilio_from_number
        ):
            return Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        logger.warning("Twilio credentials missing. Emergency features will operate in dry-run mode.")
        return None

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def _resolve_recipients(self, extra_contacts: Optional[Iterable[str]] = None) -> List[str]:
        recipients = list(self.settings.emergency_contacts)
        if self.settings.emergency_primary_number:
            recipients.append(self.settings.emergency_primary_number)
        if extra_contacts:
            recipients.extend(extra_contacts)
        # remove falsy + duplicates
        seen: set[str] = set()
        filtered: List[str] = []
        for number in recipients:
            if not number:
                continue
            normalized = number.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                filtered.append(normalized)
        return filtered

    def _build_sms_body(
        self,
        message: str,
        vitals: Dict[str, float | int | str],
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> str:
        vitals_summary = ", ".join(f"{k}: {v}" for k, v in vitals.items() if v is not None)
        location_link = _format_location_link(latitude, longitude)
        return f"{message}\nVitals -> {vitals_summary}\nLocation -> {location_link}"

    def send_sms_alert(
        self,
        reason: str,
        vitals: Dict[str, float | int | str],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        contacts: Optional[Iterable[str]] = None,
    ) -> List[str]:
        recipients = self._resolve_recipients(contacts)
        if not recipients:
            logger.warning("No emergency contacts configured; skipping SMS dispatch")
            return []

        body = self._build_sms_body(reason, vitals, latitude, longitude)
        delivered: List[str] = []

        if not self.is_configured:
            logger.info("[DRY-RUN] SMS would be sent to %s: %s", recipients, body)
            return recipients

        for number in recipients:
            try:
                self._client.messages.create(
                    body=body,
                    from_=self.settings.twilio_from_number,
                    to=number,
                )
                delivered.append(number)
            except TwilioRestException as exc:
                logger.error("Failed to send SMS to %s: %s", number, exc)
        return delivered

    def place_phone_call(
        self,
        voice_message: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        contacts: Optional[Iterable[str]] = None,
    ) -> List[str]:
        recipients = self._resolve_recipients(contacts)
        if not recipients:
            logger.warning("No emergency contacts configured; skipping voice call")
            return []

        call_script = (
            f"<Response>"
            f"<Say voice='alice'>{voice_message}</Say>"
            f"<Pause length='1'/>"
            f"<Say>Location link { _format_location_link(latitude, longitude) }</Say>"
            f"</Response>"
        )

        if not self.is_configured:
            logger.info("[DRY-RUN] Voice call would be placed to %s", recipients)
            return recipients

        placed: List[str] = []
        for number in recipients:
            try:
                self._client.calls.create(
                    twiml=call_script,
                    from_=self.settings.twilio_from_number,
                    to=number,
                )
                placed.append(number)
            except TwilioRestException as exc:
                logger.error("Failed to place call to %s: %s", number, exc)
        return placed
