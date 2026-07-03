"""
Thin wrapper around Meta's WhatsApp Business Cloud API (Graph API).
Covers: read receipts, typing indicator on/off, text/image/document sends,
and template broadcasts.

DRY-RUN MODE: if no META_ACCESS_TOKEN is configured (or a call fails), calls
are logged and skipped instead of raising — this lets the LangGraph pipeline
run end-to-end (and show up on the dashboard) even without a working WhatsApp
sandbox connection, which is useful for local demoing/testing.
"""
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("whatsapp_client")


class WhatsAppClient:
    def __init__(self, phone_number_id: str | None = None):
        # allows overriding per-tenant WABA phone number id; falls back to global
        self.phone_number_id = phone_number_id or settings.META_PHONE_NUMBER_ID
        self.base_url = f"{settings.META_GRAPH_BASE_URL}/{self.phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        self.dry_run = not settings.META_ACCESS_TOKEN

    async def _post(self, payload: dict) -> dict:
        if self.dry_run:
            logger.info("[DRY RUN] Would POST to WhatsApp: %s", payload)
            return {"messages": [{"id": "dry-run-msg-id"}]}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.base_url, headers=self.headers, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001 - never let a WhatsApp send failure kill the pipeline
            logger.warning("WhatsApp API call failed, continuing anyway: %s", e)
            return {"messages": [{"id": "failed-send"}]}

    # -------------------------------------------------------------
    # Read receipt + typing indicator
    # -------------------------------------------------------------
    async def mark_as_read(self, message_id: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return await self._post(payload)

    async def start_typing(self, message_id: str) -> dict:
        """Native WhatsApp typing indicator, tied to the inbound message id."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"},
        }
        return await self._post(payload)

    # Note: Meta auto-extinguishes the typing indicator once you send the
    # next real message (or after ~25s). We treat "sending the reply" as
    # extinguishing it -- see Dispatcher Node.

    # -------------------------------------------------------------
    # Rich media dispatch helpers
    # -------------------------------------------------------------
    async def send_text(self, to: str, body: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},  # markdown *bold* _italic_ supported natively
        }
        return await self._post(payload)

    async def send_image(self, to: str, image_url: str, caption: str | None = None) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url, **({"caption": caption} if caption else {})},
        }
        return await self._post(payload)

    async def send_document(self, to: str, doc_url: str, filename: str, caption: str | None = None) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": doc_url,
                "filename": filename,
                **({"caption": caption} if caption else {}),
            },
        }
        return await self._post(payload)

    async def send_template(self, to: str, template_name: str, language_code: str = "en_US", components: list | None = None) -> dict:
        """Used by the Broadcast Campaign Drawer to push approved template messages."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                **({"components": components} if components else {}),
            },
        }
        return await self._post(payload)
