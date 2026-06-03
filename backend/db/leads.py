"""
Lead database operations — find or create leads from inbound WhatsApp messages.
"""

from __future__ import annotations

from typing import Optional

from db.client import get_supabase
from utils.logger import get_logger
from utils.security import normalize_phone

log = get_logger(__name__)


async def find_or_create_lead(
    *,
    tenant_id: str,
    phone: str,
    source: str = "whatsapp",
    consent_given: bool = True,
) -> Optional[str]:
    """
    Upsert a lead by phone number within the tenant.
    Records WhatsApp consent on first contact.
    Returns the lead's UUID, or None on failure.
    """
    normalized = normalize_phone(phone)
    try:
        client = get_supabase()

        # Check for existing lead
        result = (
            await client.table("leads")
            .select("id, whatsapp_consent")
            .eq("tenant_id", tenant_id)
            .eq("phone", normalized)
            .limit(1)
            .execute()
        )

        if result.data:
            lead = result.data[0]
            lead_id = lead["id"]

            # Record consent if not yet captured
            if consent_given and not lead.get("whatsapp_consent"):
                await (
                    client.table("leads")
                    .update({"whatsapp_consent": True, "whatsapp_consent_source": source})
                    .eq("id", lead_id)
                    .execute()
                )
            log.info("lead_found", lead_id=lead_id, phone=normalized)
            return lead_id

        # Create new lead
        new_lead = {
            "tenant_id": tenant_id,
            "phone": normalized,
            "source": source,
            "status": "new",
            "whatsapp_consent": consent_given,
        }
        if consent_given:
            new_lead["whatsapp_consent_source"] = source

        insert_result = await client.table("leads").insert(new_lead).execute()
        if insert_result.data:
            lead_id = insert_result.data[0]["id"]
            log.info("lead_created", lead_id=lead_id, phone=normalized, source=source)
            return lead_id

    except Exception as exc:
        log.error("find_or_create_lead_error", phone=normalized, error=str(exc))

    return None


async def get_lead_by_phone(tenant_id: str, phone: str) -> Optional[dict]:
    """Return the full lead row for a given phone, or None if not found."""
    normalized = normalize_phone(phone)
    try:
        client = get_supabase()
        result = (
            await client.table("leads")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("phone", normalized)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        log.error("get_lead_by_phone_error", phone=normalized, error=str(exc))
        return None


async def get_recent_messages(
    tenant_id: str,
    phone: str,
    limit: int = 20,
) -> list[dict]:
    """Return the N most recent messages for a lead, newest first."""
    normalized = normalize_phone(phone)
    try:
        client = get_supabase()

        lead_result = (
            await client.table("leads")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("phone", normalized)
            .limit(1)
            .execute()
        )
        if not lead_result.data:
            return []

        lead_id = lead_result.data[0]["id"]
        msgs = (
            await client.table("messages")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("lead_id", lead_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return msgs.data or []
    except Exception as exc:
        log.error("get_recent_messages_error", phone=normalized, error=str(exc))
        return []
