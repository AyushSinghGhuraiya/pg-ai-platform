"""
WhatsApp webhook payload parser.
Converts raw Meta webhook JSON into typed ParsedMessage / StatusUpdate objects.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from utils.logger import get_logger

log = get_logger(__name__)

# All message types we recognise
MESSAGE_TYPES = {
    "text", "button", "interactive", "image", "audio",
    "video", "document", "location", "contacts", "sticker",
    "reaction", "unsupported",
}


class ParsedMessage(BaseModel):
    message_id: str
    from_phone: str
    to_phone: str
    timestamp: int
    message_type: str

    # text / button
    text: Optional[str] = None
    button_id: Optional[str] = None
    button_title: Optional[str] = None

    # interactive list reply
    list_id: Optional[str] = None
    list_title: Optional[str] = None

    # media
    media_url: Optional[str] = None
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None
    media_caption: Optional[str] = None

    # location
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None

    # reaction
    reaction_emoji: Optional[str] = None
    reaction_message_id: Optional[str] = None

    # reply context
    context_message_id: Optional[str] = None

    raw: dict = Field(default_factory=dict)


class StatusUpdate(BaseModel):
    message_id: str
    status: str           # sent | delivered | read | failed
    timestamp: int
    recipient_phone: str
    errors: list[dict] = Field(default_factory=list)


class WhatsAppParser:
    """Stateless parser — all methods are static."""

    @staticmethod
    def parse_webhook(payload: dict) -> list[ParsedMessage]:
        """
        Extract all inbound messages from a Meta webhook payload.
        Returns an empty list if no messages are present (e.g. status-only webhook).
        """
        messages: list[ParsedMessage] = []
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    metadata = value.get("metadata", {})
                    to_phone = metadata.get("display_phone_number", "")

                    for msg in value.get("messages", []):
                        try:
                            parsed = WhatsAppParser._parse_message(msg, to_phone)
                            messages.append(parsed)
                        except Exception as exc:
                            log.warning("whatsapp_parse_message_error", error=str(exc), msg=msg)
        except Exception as exc:
            log.error("whatsapp_parse_webhook_error", error=str(exc))
        return messages

    @staticmethod
    def parse_statuses(payload: dict) -> list[StatusUpdate]:
        """Extract all delivery/read status updates from a Meta webhook payload."""
        statuses: list[StatusUpdate] = []
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for status in value.get("statuses", []):
                        try:
                            statuses.append(StatusUpdate(
                                message_id=status["id"],
                                status=status["status"],
                                timestamp=int(status["timestamp"]),
                                recipient_phone=status.get("recipient_id", ""),
                                errors=status.get("errors", []),
                            ))
                        except Exception as exc:
                            log.warning("whatsapp_parse_status_error", error=str(exc), status=status)
        except Exception as exc:
            log.error("whatsapp_parse_statuses_error", error=str(exc))
        return statuses

    @staticmethod
    def _parse_message(msg: dict, to_phone: str) -> ParsedMessage:
        msg_type = WhatsAppParser._extract_message_type(msg)
        base = dict(
            message_id=msg["id"],
            from_phone=msg["from"],
            to_phone=to_phone,
            timestamp=int(msg["timestamp"]),
            message_type=msg_type,
            raw=msg,
        )

        # reply context
        if "context" in msg:
            base["context_message_id"] = msg["context"].get("id")

        if msg_type == "text":
            base["text"] = msg.get("text", {}).get("body", "")

        elif msg_type == "button":
            btn = msg.get("button", {})
            base["button_id"] = btn.get("payload", "")
            base["button_title"] = btn.get("text", "")
            base["text"] = btn.get("text", "")

        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type", "")
            if itype == "button_reply":
                reply = interactive.get("button_reply", {})
                base["message_type"] = "interactive.button_reply"
                base["button_id"] = reply.get("id", "")
                base["button_title"] = reply.get("title", "")
                base["text"] = reply.get("title", "")
            elif itype == "list_reply":
                reply = interactive.get("list_reply", {})
                base["message_type"] = "interactive.list_reply"
                base["list_id"] = reply.get("id", "")
                base["list_title"] = reply.get("title", "")
                base["text"] = reply.get("title", "")
            else:
                base["message_type"] = "unsupported"

        elif msg_type in {"image", "audio", "video", "document", "sticker"}:
            media = msg.get(msg_type, {})
            base["media_id"] = media.get("id")
            base["media_mime_type"] = media.get("mime_type")
            base["media_url"] = media.get("url")  # only present after media retrieval
            if msg_type in {"image", "video", "document"}:
                base["media_caption"] = media.get("caption")

        elif msg_type == "location":
            loc = msg.get("location", {})
            base["location_lat"] = loc.get("latitude")
            base["location_lng"] = loc.get("longitude")
            base["location_name"] = loc.get("name")
            base["location_address"] = loc.get("address")

        elif msg_type == "reaction":
            reaction = msg.get("reaction", {})
            base["reaction_emoji"] = reaction.get("emoji")
            base["reaction_message_id"] = reaction.get("message_id")

        # contacts and unsupported fall through with just the base fields

        return ParsedMessage(**base)

    @staticmethod
    def _extract_message_type(msg: dict) -> str:
        raw_type = msg.get("type", "unsupported")
        return raw_type if raw_type in MESSAGE_TYPES else "unsupported"


# Module-level convenience instance
whatsapp_parser = WhatsAppParser()
