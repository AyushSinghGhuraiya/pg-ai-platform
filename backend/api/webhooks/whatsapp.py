"""
WhatsApp Cloud API webhook endpoints.

GET  /webhook/whatsapp  — Meta hub verification (one-time setup)
POST /webhook/whatsapp  — Inbound messages & status updates

Security: HMAC-SHA256 signature verified on every POST before processing.
Processing is offloaded to BackgroundTasks so Meta always gets 200 within 5s.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from config import settings
from services.whatsapp_processor import process_webhook
from utils.logger import get_logger
from utils.security import verify_meta_signature

router = APIRouter()
log = get_logger(__name__)


@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request) -> Response:
    """
    Meta sends a GET with hub.mode, hub.verify_token, hub.challenge.
    We must echo back hub.challenge with 200 to activate the webhook.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")

    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        log.info("whatsapp_webhook_verified")
        return Response(content=challenge, media_type="text/plain")

    log.warning("whatsapp_webhook_verify_failed", mode=mode, token_match=token == settings.whatsapp_verify_token)
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhook/whatsapp")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Receive all inbound events from Meta (messages + status updates).
    - Verify HMAC signature first; return 401 on failure.
    - Offload processing to background so we return 200 immediately.
    - Never return non-200 for auth-valid payloads (Meta would retry forever).
    """
    raw_body = await request.body()

    # HMAC verification — reject unauthenticated requests
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_signature(raw_body, signature, settings.whatsapp_app_secret):
        log.warning("whatsapp_signature_invalid", signature=signature)
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        log.warning("whatsapp_invalid_json")
        # Return 200 so Meta doesn't keep retrying a malformed payload
        return {"status": "ok"}

    object_type = payload.get("object")
    if object_type != "whatsapp_business_account":
        log.info("whatsapp_webhook_non_wa_event", object=object_type)
        return {"status": "ok"}

    background_tasks.add_task(process_webhook, payload)
    log.info("whatsapp_webhook_queued")
    return {"status": "ok"}
