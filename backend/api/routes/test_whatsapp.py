"""
Test / debug routes for WhatsApp integration.
Only fully functional in development; requests are logged and rate-limited by caller.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from db.leads import get_recent_messages
from services.whatsapp import whatsapp_service
from services.whatsapp_processor import process_webhook
from utils.logger import get_logger
from utils.security import validate_phone

router = APIRouter(prefix="/test/whatsapp", tags=["test-whatsapp"])
log = get_logger(__name__)


# ── Request models ────────────────────────────────────────────────────────────

class SendTextRequest(BaseModel):
    phone: Optional[str] = None   # defaults to TEST_WHATSAPP_NUMBER
    text: str


class SendTemplateRequest(BaseModel):
    phone: Optional[str] = None
    template_name: str
    language_code: str = "en_US"
    components: Optional[list] = None


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/send-text")
async def send_text(req: SendTextRequest) -> dict:
    phone = _resolve_phone(req.phone)
    result = await whatsapp_service.send_text(phone, req.text)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {"phone": phone, "message_id": result["message_id"]}


@router.post("/send-template")
async def send_template(req: SendTemplateRequest) -> dict:
    phone = _resolve_phone(req.phone)
    result = await whatsapp_service.send_template(
        phone,
        req.template_name,
        language_code=req.language_code,
        components=req.components,
    )
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {"phone": phone, "message_id": result["message_id"]}


@router.post("/send-buttons")
async def send_buttons(req: SendButtonsRequest) -> dict:
    phone = _resolve_phone(req.phone)
    result = await whatsapp_service.send_buttons(
        phone,
        req.body_text,
        req.buttons,
        header_text=req.header_text,
        footer_text=req.footer_text,
    )
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {"phone": phone, "message_id": result["message_id"]}


@router.get("/messages/{phone}")
async def get_messages(phone: str, limit: int = 20) -> dict:
    """Fetch recent DB messages for a phone number (for smoke-testing)."""
    messages = await get_recent_messages(
        tenant_id=settings.default_tenant_id,
        phone=phone,
        limit=limit,
    )
    return {"phone": phone, "count": len(messages), "messages": messages}


@router.post("/simulate-webhook")
async def simulate_webhook(payload: dict) -> dict:
    """
    Replay a raw Meta webhook payload through the full processor pipeline.
    Useful for testing parsing + DB writes without needing a real message.
    """
    if settings.is_production:
        raise HTTPException(status_code=403, detail="Not available in production")
    await process_webhook(payload)
    return {"status": "processed"}
