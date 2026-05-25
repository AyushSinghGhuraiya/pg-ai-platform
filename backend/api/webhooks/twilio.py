"""
Twilio WhatsApp webhook endpoints.

POST /webhooks/twilio/whatsapp        — inbound messages
POST /webhooks/twilio/whatsapp/status — delivery status callbacks

Twilio sends application/x-www-form-urlencoded (form data, NOT JSON).
Response must be TwiML XML (even if empty) — Twilio ignores non-XML 200s.
Security: X-Twilio-Signature HMAC verified on every POST.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import Response

from config import settings
from services.twilio_parser import twilio_parser
from utils.logger import get_logger
from utils.security import verify_twilio_signature

router = APIRouter()
log = get_logger(__name__)

_TWIML_EMPTY = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _twiml() -> Response:
    return Response(content=_TWIML_EMPTY, media_type="application/xml")


@router.post("/webhooks/twilio/whatsapp")
async def receive_twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: str = Header(default=""),
) -> Response:
    """Receive inbound WhatsApp messages from Twilio."""
    form_data = await request.form()
    form_dict = dict(form_data)

    # Signature verification — use full public URL (ngrok or prod)
    full_url = str(request.url)
    if not verify_twilio_signature(
        signature=x_twilio_signature,
        url=full_url,
        params=form_dict,
        auth_token=settings.twilio_auth_token,
    ):
        log.warning("twilio_signature_invalid", url=full_url)
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    log.info(
        "twilio_webhook_received",
        from_=form_dict.get("From"),
        sid=form_dict.get("MessageSid"),
    )

    background_tasks.add_task(_process_inbound, form_dict)
    return _twiml()


@router.post("/webhooks/twilio/whatsapp/status")
async def receive_twilio_status(
    request: Request,
    x_twilio_signature: str = Header(default=""),
) -> Response:
    """Receive delivery/read status callbacks from Twilio."""
    form_data = await request.form()
    form_dict = dict(form_data)

    full_url = str(request.url)
    if not verify_twilio_signature(
        signature=x_twilio_signature,
        url=full_url,
        params=form_dict,
        auth_token=settings.twilio_auth_token,
    ):
        log.warning("twilio_status_signature_invalid")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    status_update = twilio_parser.parse_status_callback(form_dict)
    if status_update:
        from db.messages import update_message_status
        await update_message_status(status_update.message_id, status_update.status)
        log.info(
            "twilio_status_updated",
            sid=status_update.message_id,
            status=status_update.status,
        )
    return _twiml()


async def _process_inbound(form_dict: dict) -> None:
    """Parse and process an inbound Twilio message in the background."""
    try:
        msg = twilio_parser.parse_webhook(form_dict)
        if not msg:
            log.warning("twilio_parse_returned_none", form=form_dict)
            return
        from services.whatsapp_processor import process_message
        await process_message(msg)
    except Exception as exc:
        log.error("twilio_process_error", error=str(exc))
