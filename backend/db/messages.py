"""
Database operations for WhatsApp messages.
"""

from __future__ import annotations

from typing import Optional

from db.client import get_supabase
from utils.logger import get_logger

log = get_logger(__name__)


async def message_already_processed(message_id: str) -> bool:
    """Return True if this Meta message_id already exists in the DB (idempotency check)."""
    try:
        client = await get_supabase()
        result = (
            await client.table("messages")
            .select("id")
            .eq("whatsapp_message_id", message_id)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0
    except Exception as exc:
        log.error("db_check_message_error", message_id=message_id, error=str(exc))
        return False


async def save_inbound_message(
    *,
    tenant_id: str,
    lead_id: str,
    message_id: str,
    from_phone: str,
    message_type: str,
    content: Optional[str] = None,
    raw_payload: Optional[dict] = None,
    media_url: Optional[str] = None,
    media_id: Optional[str] = None,
) -> Optional[str]:
    """
    Persist an inbound WhatsApp message.
    Returns the DB row id on success, None on failure.
    """
    try:
        client = await get_supabase()
        row = {
            "tenant_id": tenant_id,
            "lead_id": lead_id,
            "whatsapp_message_id": message_id,
            "direction": "inbound",
            "message_type": message_type,
            "content": content,
            "from_phone": from_phone,
            "raw_payload": raw_payload or {},
            "status": "received",
        }
        if media_url:
            row["media_url"] = media_url
        if media_id:
            row["media_id"] = media_id

        result = await client.table("messages").insert(row).execute()
        if result.data:
            db_id = result.data[0]["id"]
            log.info("message_saved", direction="inbound", db_id=db_id, message_id=message_id)
            return db_id
    except Exception as exc:
        log.error("save_inbound_message_error", message_id=message_id, error=str(exc))
    return None


async def save_outbound_message(
    *,
    tenant_id: str,
    lead_id: str,
    message_id: str,
    to_phone: str,
    message_type: str,
    content: Optional[str] = None,
    template_name: Optional[str] = None,
) -> Optional[str]:
    """Persist an outbound WhatsApp message. Returns the DB row id."""
    try:
        client = await get_supabase()
        row = {
            "tenant_id": tenant_id,
            "lead_id": lead_id,
            "whatsapp_message_id": message_id,
            "direction": "outbound",
            "message_type": message_type,
            "content": content,
            "to_phone": to_phone,
            "status": "sent",
        }
        if template_name:
            row["template_name"] = template_name

        result = await client.table("messages").insert(row).execute()
        if result.data:
            db_id = result.data[0]["id"]
            log.info("message_saved", direction="outbound", db_id=db_id, message_id=message_id)
            return db_id
    except Exception as exc:
        log.error("save_outbound_message_error", message_id=message_id, error=str(exc))
    return None


async def update_message_status(message_id: str, status: str) -> bool:
    """Update delivery status (sent → delivered → read) by whatsapp_message_id."""
    try:
        client = await get_supabase()
        await (
            client.table("messages")
            .update({"status": status})
            .eq("whatsapp_message_id", message_id)
            .execute()
        )
        log.info("message_status_updated", message_id=message_id, status=status)
        return True
    except Exception as exc:
        log.error("update_message_status_error", message_id=message_id, error=str(exc))
        return False
