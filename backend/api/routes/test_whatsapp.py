"""
Test / debug routes for WhatsApp integration.
Supports both Meta and Twilio providers.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from db.leads import get_recent_messages
from services.whatsapp_adapter import whatsapp_adapter
from services.whatsapp_processor import process_webhook
from utils.logger import get_logger
from utils.security import validate_phone

router = APIRouter(prefix="/test/whatsapp", tags=["test-whatsapp"])
log = get_logger(__name__)


# ── Request models ────────────────────────────────────────────────────────────

class SendTextRequest(BaseModel):
    phone: Optional[str] = None
    text: str


class SendTemplateRequest(BaseModel):
    phone: Optional[str] = None
    template_name: str
    language_code: str = "en_US"
    components: Optional[list] = None
    body: Optional[str] = None


class SendButtonsRequest(BaseModel):
    phone: Optional[str] = None
    body_text: str
    buttons: list[dict]
    header_text: Optional[str] = None
    footer_text: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_phone(phone: Optional[str]) -> str:
    target = phone or settings.test_whatsapp_number
    if not target:
        raise HTTPException(status_code=400, detail="No phone provided and TEST_WHATSAPP_NUMBER not set")
    if not validate_phone(target):
        raise HTTPException(status_code=422, detail=f"Invalid phone number: {target}")
    return target


# ── Endpoints — use active provider (adapter) ─────────────────────────────────

@router.get("/check-provider")
async def check_provider() -> dict:
    """Return which WhatsApp provider is currently active."""
    return {
        "provider": settings.whatsapp_provider,
        "twilio_configured": settings.twilio_configured,
        "meta_configured": bool(settings.whatsapp_access_token),
        "test_number": settings.test_whatsapp_number,
    }


@router.post("/send-text")
async def send_text(req: SendTextRequest) -> dict:
    """Send text via the active provider (adapter)."""
    phone = _resolve_phone(req.phone)
    result = await whatsapp_adapter.send_text(phone, req.text)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=str(result.get("error")))
    return {"provider": whatsapp_adapter.provider, "phone": phone, "message_id": result["message_id"]}


@router.post("/send-template")
async def send_template(req: SendTemplateRequest) -> dict:
    phone = _resolve_phone(req.phone)
    result = await whatsapp_adapter.send_template(
        phone,
        req.template_name,
        language_code=req.language_code,
        components=req.components,
        body=req.body,
    )
    if not result["success"]:
        raise HTTPException(status_code=502, detail=str(result.get("error")))
    return {"provider": whatsapp_adapter.provider, "phone": phone, "message_id": result["message_id"]}


@router.post("/send-buttons")
async def send_buttons(req: SendButtonsRequest) -> dict:
    phone = _resolve_phone(req.phone)
    result = await whatsapp_adapter.send_buttons(
        phone,
        req.body_text,
        req.buttons,
        header_text=req.header_text,
        footer_text=req.footer_text,
    )
    if not result["success"]:
        raise HTTPException(status_code=502, detail=str(result.get("error")))
    return {"provider": whatsapp_adapter.provider, "phone": phone, "message_id": result["message_id"]}


# ── Twilio-specific endpoints ─────────────────────────────────────────────────

@router.post("/twilio/send-text")
async def twilio_send_text(req: SendTextRequest) -> dict:
    """Force send via Twilio regardless of active provider."""
    phone = _resolve_phone(req.phone)
    from services.twilio_whatsapp import TwilioWhatsAppService
    svc = TwilioWhatsAppService()
    svc.init()
    result = await svc.send_text(phone, req.text)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=str(result.get("error")))
    return {"provider": "twilio", "phone": phone, "message_id": result["message_id"]}


# ── Shared endpoints ──────────────────────────────────────────────────────────

@router.get("/messages/{phone}")
async def get_messages(phone: str, limit: int = 20) -> dict:
    """Fetch recent DB messages for a phone number."""
    messages = await get_recent_messages(
        tenant_id=settings.default_tenant_id,
        phone=phone,
        limit=limit,
    )
    return {"phone": phone, "count": len(messages), "messages": messages}


@router.post("/simulate-webhook")
async def simulate_webhook(payload: dict) -> dict:
    """Replay a raw Meta webhook payload through the processor pipeline."""
    if settings.is_production:
        raise HTTPException(status_code=403, detail="Not available in production")
    await process_webhook(payload)
    return {"status": "processed"}
