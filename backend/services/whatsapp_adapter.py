"""
Unified WhatsApp adapter.
Routes send_text / send_buttons / etc. to Twilio OR Meta based on WHATSAPP_PROVIDER config.
The rest of the codebase imports `whatsapp_adapter` and never knows which provider is active.
"""

from __future__ import annotations

from typing import Optional

from config import settings
from utils.logger import get_logger

log = get_logger(__name__)


class WhatsAppAdapter:
    """Thin router — delegates every method to the active provider service."""

    def __init__(self) -> None:
        self._service = None

    def init(self) -> None:
        provider = settings.whatsapp_provider.lower()
        if provider == "twilio":
            from services.twilio_whatsapp import TwilioWhatsAppService
            self._service = TwilioWhatsAppService()
            self._service.init()
        elif provider == "meta":
            from services.whatsapp import WhatsAppService
            self._service = WhatsAppService()
            self._service.init()
        else:
            raise ValueError(f"Unknown WHATSAPP_PROVIDER: {provider!r}. Use 'twilio' or 'meta'.")
        log.info("whatsapp_adapter_ready", provider=provider)

    async def close(self) -> None:
        if self._service:
            await self._service.close()

    @property
    def provider(self) -> str:
        return settings.whatsapp_provider.lower()

    # ── Delegate all send methods ──────────────────────────────────────────────

    async def send_text(self, phone: str, text: str, **kwargs) -> dict:
        return await self._service.send_text(phone, text, **kwargs)

    async def send_template(self, phone: str, template_name: str, **kwargs) -> dict:
        return await self._service.send_template(phone, template_name, **kwargs)

    async def send_buttons(
        self,
        phone: str,
        body_text: str,
        buttons: list[dict],
        **kwargs,
    ) -> dict:
        return await self._service.send_buttons(phone, body_text, buttons, **kwargs)

    async def send_list(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        **kwargs,
    ) -> dict:
        return await self._service.send_list(phone, body_text, button_text, sections, **kwargs)

    async def send_image(self, phone: str, image_url: str, caption: Optional[str] = None) -> dict:
        return await self._service.send_image(phone, image_url, caption)

    async def send_location(
        self,
        phone: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> dict:
        return await self._service.send_location(phone, latitude, longitude, name, address)

    async def mark_as_read(self, message_id: str) -> dict:
        return await self._service.mark_as_read(message_id)


# Module-level singleton — used everywhere in the codebase
whatsapp_adapter = WhatsAppAdapter()
