"""
WhatsApp Cloud API outbound service.
All messages go through here — text, templates, buttons, lists, media.

Meta base URL: https://graph.facebook.com/v19.0/{phone_number_id}/messages
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from config import settings
from utils.logger import get_logger
from utils.security import normalize_phone, to_whatsapp_phone

log = get_logger(__name__)

_GRAPH_VERSION = "v19.0"
_BASE_URL = f"https://graph.facebook.com/{_GRAPH_VERSION}"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Retry on these status codes
_RETRY_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


class WhatsAppService:
    """Singleton outbound WhatsApp service. Initialise once via init()."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._phone_id: str = settings.whatsapp_phone_number_id
        self._token: str = settings.whatsapp_access_token

    def init(self) -> None:
        """Create the httpx client. Call at startup."""
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )
        log.info("whatsapp_service_ready", phone_id=self._phone_id)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    # ── Internal send helper ──────────────────────────────────────────────────

    async def _send(self, payload: dict) -> dict:
        """POST to messages endpoint with retry on rate-limit / 5xx."""
        if not self._client:
            raise RuntimeError("WhatsAppService not initialised — call init() first")

        url = f"/{self._phone_id}/messages"
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                t0 = time.perf_counter()
                resp = await self._client.post(url, json=payload)
                latency_ms = round((time.perf_counter() - t0) * 1000)

                if resp.status_code in _RETRY_CODES and attempt < _MAX_RETRIES:
                    wait = 2 ** attempt
                    log.warning("whatsapp_retry", status=resp.status_code, attempt=attempt, wait_s=wait)
                    import asyncio; await asyncio.sleep(wait)
                    continue

                data = resp.json()
                if resp.status_code >= 400:
                    log.error("whatsapp_api_error", status=resp.status_code, body=data)
                    return {"success": False, "error": data, "message_id": None}

                message_id = (
                    data.get("messages", [{}])[0].get("id")
                    if data.get("messages")
                    else None
                )
                log.info("whatsapp_sent", message_id=message_id, latency_ms=latency_ms)
                return {"success": True, "message_id": message_id, "raw": data}

            except httpx.RequestError as exc:
                log.warning("whatsapp_request_error", attempt=attempt, error=str(exc))
                last_exc = exc

        return {"success": False, "error": str(last_exc), "message_id": None}

    # ── Public send methods ───────────────────────────────────────────────────

    async def send_text(
        self,
        phone: str,
        text: str,
        preview_url: bool = False,
        context_message_id: Optional[str] = None,
    ) -> dict:
        """Send a plain text message. Must be inside 24-hour conversation window."""
        to = to_whatsapp_phone(normalize_phone(phone))
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        return await self._send(payload)

    async def send_template(
        self,
        phone: str,
        template_name: str,
        language_code: str = "en_US",
        components: Optional[list] = None,
    ) -> dict:
        """
        Send a pre-approved template message.
        Use this to initiate a conversation (outside 24h window).
        components example: [{"type": "body", "parameters": [{"type": "text", "text": "Ayush"}]}]
        """
        to = to_whatsapp_phone(normalize_phone(phone))
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        return await self._send(payload)

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
        Send interactive reply buttons (max 3).
        buttons: [{"id": "btn_1", "title": "Boys PG"}, ...]
        """
        to = to_whatsapp_phone(normalize_phone(phone))
        interactive: dict[str, Any] = {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                    for b in buttons[:3]
                ]
            },
        }
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        return await self._send(payload)

    async def send_list(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> dict:
        """
        Send a list message (up to 10 items across all sections).
        sections: [{"title": "Sectors", "rows": [{"id": "s22", "title": "Sector 22", "description": "..."}]}]
        """
        to = to_whatsapp_phone(normalize_phone(phone))
        interactive: dict[str, Any] = {
            "type": "list",
            "body": {"text": body_text},
            "action": {"button": button_text, "sections": sections},
        }
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._send(payload)

    async def send_image(
        self,
        phone: str,
        image_url: str,
        caption: Optional[str] = None,
    ) -> dict:
        """Send an image by URL (must be publicly accessible)."""
        to = to_whatsapp_phone(normalize_phone(phone))
        image: dict[str, Any] = {"link": image_url}
        if caption:
            image["caption"] = caption
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": image,
        }
        return await self._send(payload)

    async def send_location(
        self,
        phone: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> dict:
        """Send a location pin."""
        to = to_whatsapp_phone(normalize_phone(phone))
        location: dict[str, Any] = {"latitude": latitude, "longitude": longitude}
        if name:
            location["name"] = name
        if address:
            location["address"] = address
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "location",
            "location": location,
        }
        return await self._send(payload)

    async def mark_as_read(self, message_id: str) -> dict:
        """
        Mark a received message as read.
        This shows the blue double-tick on the sender's phone.
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return await self._send(payload)


# ── Module-level singleton ────────────────────────────────────────────────────

whatsapp_service = WhatsAppService()
