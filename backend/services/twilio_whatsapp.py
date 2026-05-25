"""
Twilio WhatsApp outbound service.
Drop-in replacement for Meta WhatsAppService — same method signatures.
"""

from __future__ import annotations

from typing import Optional

from config import settings
from utils.logger import get_logger
from utils.security import from_twilio_format, normalize_phone, to_twilio_format

log = get_logger(__name__)


class TwilioWhatsAppService:
    """Singleton outbound WhatsApp service via Twilio REST API."""

    def __init__(self) -> None:
        self._client = None
        self._from_number: str = ""

    def init(self) -> None:
        """Create Twilio client. Call at startup."""
        from twilio.rest import Client
        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._from_number = to_twilio_format(settings.twilio_whatsapp_number)
        log.info("twilio_service_ready", from_number=self._from_number)

    def _to(self, phone: str) -> str:
        """Normalise phone and convert to Twilio whatsapp: format."""
        return to_twilio_format(normalize_phone(phone))

    def _send(self, to: str, body: str = "", media_url: Optional[str] = None) -> dict:
        """Send a message via Twilio and return standardised result dict."""
        if not self._client:
            raise RuntimeError("TwilioWhatsAppService not initialised — call init() first")
        try:
            kwargs: dict = {"from_": self._from_number, "to": to, "body": body}
            if media_url:
                kwargs["media_url"] = [media_url]

            msg = self._client.messages.create(**kwargs)
            log.info("twilio_sent", sid=msg.sid, to=to, status=msg.status)
            return {"success": True, "message_id": msg.sid, "status": msg.status}
        except Exception as exc:
            log.error("twilio_send_error", to=to, error=str(exc))
            return {"success": False, "error": str(exc), "message_id": None}

    # ── Public send methods ────────────────────────────────────────────────────

    async def send_text(
        self,
        phone: str,
        text: str,
        preview_url: bool = False,
        context_message_id: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> dict:
        return self._send(self._to(phone), body=text, media_url=media_url)

    async def send_template(
        self,
        phone: str,
        template_name: Optional[str] = None,
        language_code: str = "en_US",
        components: Optional[list] = None,
        body: Optional[str] = None,
        content_sid: Optional[str] = None,
        content_variables: Optional[dict] = None,
    ) -> dict:
        """
        Send via Twilio Content API (content_sid) or plain text fallback.
        Twilio Sandbox only supports plain text and hello_world equivalent.
        """
        if content_sid:
            if not self._client:
                raise RuntimeError("TwilioWhatsAppService not initialised")
            try:
                import json
                kwargs: dict = {
                    "from_": self._from_number,
                    "to": self._to(phone),
                    "content_sid": content_sid,
                }
                if content_variables:
                    kwargs["content_variables"] = json.dumps(content_variables)
                msg = self._client.messages.create(**kwargs)
                log.info("twilio_template_sent", sid=msg.sid, content_sid=content_sid)
                return {"success": True, "message_id": msg.sid, "status": msg.status}
            except Exception as exc:
                log.error("twilio_template_error", error=str(exc))
                return {"success": False, "error": str(exc), "message_id": None}

        # Fallback: plain text body
        text = body or f"[{template_name or 'message'}]"
        return self._send(self._to(phone), body=text)

    async def send_buttons(
        self,
        phone: str,
        body_text: str,
        buttons: list[dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        context_message_id: Optional[str] = None,
    ) -> dict:
        """
        Twilio Sandbox doesn't support interactive buttons natively.
        Fall back to numbered text options.
        """
        lines = []
        if header_text:
            lines.append(f"*{header_text}*\n")
        lines.append(body_text)
        lines.append("")
        for i, btn in enumerate(buttons[:3], 1):
            lines.append(f"{i}. {btn.get('title', btn.get('id', ''))}")
        if footer_text:
            lines.append(f"\n_{footer_text}_")
        return self._send(self._to(phone), body="\n".join(lines))

    async def send_list(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> dict:
        """Twilio Sandbox: fall back to numbered text list."""
        lines = []
        if header_text:
            lines.append(f"*{header_text}*\n")
        lines.append(body_text)
        n = 1
        for section in sections:
            if section.get("title"):
                lines.append(f"\n*{section['title']}*")
            for row in section.get("rows", []):
                lines.append(f"{n}. {row.get('title', '')}")
                if row.get("description"):
                    lines.append(f"   {row['description']}")
                n += 1
        if footer_text:
            lines.append(f"\n_{footer_text}_")
        return self._send(self._to(phone), body="\n".join(lines))

    async def send_image(
        self,
        phone: str,
        image_url: str,
        caption: Optional[str] = None,
    ) -> dict:
        return self._send(self._to(phone), body=caption or "", media_url=image_url)

    async def send_location(
        self,
        phone: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> dict:
        label = name or "Location"
        if address:
            label += f"\n{address}"
        text = f"📍 {label}\nhttps://maps.google.com/?q={latitude},{longitude}"
        return self._send(self._to(phone), body=text)

    async def mark_as_read(self, message_id: str) -> dict:
        """Twilio doesn't support mark-as-read — no-op."""
        return {"success": True, "message_id": message_id}

    async def close(self) -> None:
        """No persistent connection to close."""
        pass


twilio_whatsapp_service = TwilioWhatsAppService()
