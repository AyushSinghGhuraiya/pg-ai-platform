"""
WhatsApp webhook processor.
Orchestrates: parse → idempotency → lead upsert → DB save → mark-as-read.
Always returns without raising — caller must return 200 to Meta regardless.
"""

from __future__ import annotations

from config import settings
from db.leads import find_or_create_lead
from db.messages import (
    message_already_processed,
    save_inbound_message,
    update_message_status,
)
from services.whatsapp import whatsapp_service
from services.whatsapp_parser import ParsedMessage, StatusUpdate, whatsapp_parser
from utils.logger import get_logger

log = get_logger(__name__)

_TENANT_ID = settings.default_tenant_id


async def process_webhook(payload: dict) -> None:
    """Entry point called by the webhook route via BackgroundTasks."""
    messages = whatsapp_parser.parse_webhook(payload)
    statuses = whatsapp_parser.parse_statuses(payload)

    for msg in messages:
        await process_message(msg)

    for status in statuses:
        await process_status_update(status)


async def process_message(msg: ParsedMessage) -> None:
    """
    Handle a single inbound message:
    1. Idempotency check
    2. Upsert lead
    3. Persist message
    4. Mark as read
    """
    try:
        # 1. Idempotency
        if await message_already_processed(msg.message_id):
            log.info("message_duplicate_skipped", message_id=msg.message_id)
            return

        log.info(
            "message_received",
            message_id=msg.message_id,
            from_phone=msg.from_phone,
            type=msg.message_type,
        )

        # 2. Upsert lead
        lead_id = await find_or_create_lead(
            tenant_id=_TENANT_ID,
            phone=msg.from_phone,
            source="whatsapp",
            consent_given=True,
        )
        if not lead_id:
            log.error("process_message_no_lead", message_id=msg.message_id)
            return

        # 3. Persist
        content = (
            msg.text
            or msg.button_title
            or msg.list_title
            or msg.reaction_emoji
            or None
        )
        await save_inbound_message(
            tenant_id=_TENANT_ID,
            lead_id=lead_id,
            message_id=msg.message_id,
            from_phone=msg.from_phone,
            message_type=msg.message_type,
            content=content,
            raw_payload=msg.raw,
            media_url=msg.media_url,
            media_id=msg.media_id,
        )

        # 4. Mark as read (best-effort — never let this block the pipeline)
        try:
            await whatsapp_service.mark_as_read(msg.message_id)
        except Exception as exc:
            log.warning("mark_as_read_failed", message_id=msg.message_id, error=str(exc))

    except Exception as exc:
        log.error("process_message_error", message_id=msg.message_id, error=str(exc))


async def process_status_update(status: StatusUpdate) -> None:
    """Update delivery / read status for an outbound message."""
    try:
        await update_message_status(status.message_id, status.status)
        if status.errors:
            log.warning(
                "whatsapp_delivery_error",
                message_id=status.message_id,
                errors=status.errors,
            )
    except Exception as exc:
        log.error("process_status_error", message_id=status.message_id, error=str(exc))
