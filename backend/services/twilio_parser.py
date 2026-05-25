"""
Twilio WhatsApp webhook payload parser.
Twilio sends application/x-www-form-urlencoded (form data), NOT JSON.
Converts to the same ParsedMessage / StatusUpdate models used by the Meta parser.
"""

from __future__ import annotations

from typing import Optional

from services.whatsapp_parser import ParsedMessage, StatusUpdate
from utils.logger import get_logger
from utils.security import from_twilio_format, normalize_phone

log = get_logger(__name__)

# Twilio status values map directly to our internal statuses
_STATUS_MAP = {
    "sent": "sent",
    "delivered": "delivered",
    "read": "read",
    "failed": "failed",
    "undelivered": "failed",
    "queued": "sent",
    "sending": "sent",
}


class TwilioWhatsAppParser:
    """Stateless parser — all methods are static."""

    @staticmethod
    def parse_webhook(form: dict) -> Optional[ParsedMessage]:
        """
        Parse a Twilio inbound webhook (form data dict) into a ParsedMessage.
        Returns None if the payload is a status callback, not an inbound message.
        """
        # Status callbacks don't have a Body / From direction we care about
        message_sid = form.get("MessageSid") or form.get("SmsMessageSid")
        from_raw = form.get("From", "")
        to_raw = form.get("To", "")

        if not message_sid or not from_raw:
            return None

        # Strip whatsapp: prefix
        from_phone = normalize_phone(from_twilio_format(from_raw))
        to_phone = from_twilio_format(to_raw)

        # Detect message type
        num_media = int(form.get("NumMedia", "0") or "0")
        latitude = form.get("Latitude")
        longitude = form.get("Longitude")
        button_text = form.get("ButtonText") or form.get("ButtonPayload")

        body = form.get("Body", "").strip()

        msg_type = "text"
        media_url: Optional[str] = None
        media_mime: Optional[str] = None
        location_lat: Optional[float] = None
        location_lng: Optional[float] = None
        btn_id: Optional[str] = None
        btn_title: Optional[str] = None

        if latitude and longitude:
            msg_type = "location"
            location_lat = float(latitude)
            location_lng = float(longitude)
        elif button_text:
            msg_type = "interactive.button_reply"
            btn_id = form.get("ButtonPayload", button_text)
            btn_title = button_text
        elif num_media > 0:
            mime = form.get("MediaContentType0", "")
            media_url = form.get("MediaUrl0")
            if mime.startswith("image/"):
                msg_type = "image"
            elif mime.startswith("audio/"):
                msg_type = "audio"
            elif mime.startswith("video/"):
                msg_type = "video"
            elif mime.startswith("application/"):
                msg_type = "document"
            else:
                msg_type = "image"  # safe fallback for media
            media_mime = mime

        try:
            return ParsedMessage(
                message_id=message_sid,
                from_phone=from_phone,
                to_phone=to_phone,
                timestamp=int(form.get("Timestamp", "0") or "0"),
                message_type=msg_type,
                text=body or None,
                button_id=btn_id,
                button_title=btn_title,
                media_url=media_url,
                media_mime_type=media_mime,
                location_lat=location_lat,
                location_lng=location_lng,
                raw={**form, "_provider": "twilio"},
            )
        except Exception as exc:
            log.error("twilio_parse_error", error=str(exc), form=form)
            return None

    @staticmethod
    def parse_status_callback(form: dict) -> Optional[StatusUpdate]:
        """Parse a Twilio status callback into a StatusUpdate."""
        message_sid = form.get("MessageSid") or form.get("SmsSid")
        status_raw = form.get("MessageStatus") or form.get("SmsStatus", "")
        recipient_raw = form.get("To", "")

        if not message_sid:
            return None

        status = _STATUS_MAP.get(status_raw, status_raw)
        recipient = normalize_phone(from_twilio_format(recipient_raw))

        errors = []
        if form.get("ErrorCode"):
            errors = [{"code": form["ErrorCode"], "message": form.get("ErrorMessage", "")}]

        try:
            return StatusUpdate(
                message_id=message_sid,
                status=status,
                timestamp=0,
                recipient_phone=recipient,
                errors=errors,
            )
        except Exception as exc:
            log.error("twilio_status_parse_error", error=str(exc))
            return None


twilio_parser = TwilioWhatsAppParser()
