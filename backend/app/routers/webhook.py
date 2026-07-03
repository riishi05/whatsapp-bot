"""
Task 4: Async Webhook Handler
- GET  /api/webhooks/whatsapp  -> Meta's verification challenge
- POST /api/webhooks/whatsapp  -> inbound message intake, returns 200 OK
  immediately and processes the LangGraph agent in a background task.

Bonus: X-Hub-Signature-256 validation to confirm payloads originate from Meta.
"""
import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response

from app.config import get_settings
from app.graph.graph import run_agent

router = APIRouter(prefix="/api/webhooks", tags=["webhook"])
settings = get_settings()
logger = logging.getLogger("webhook")


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not settings.META_APP_SECRET:
        return True  # signature check disabled if no secret configured (local dev)
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(settings.META_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected, provided)


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


def _resolve_tenant_id(phone_number_id: str) -> str:
    """
    Multiple tenants can share this backend but have distinct WABA
    phone_number_id values. In a fuller build this would look up the tenant
    by whatsapp_phone_number_id in Mongo; kept synchronous+simple here and
    the async DB lookup happens inside context_retriever using tenant_id,
    so we resolve tenant_id via a cached map built at startup (see main.py)
    or fall back to a default tenant for sandbox testing.
    """
    from app.tenant_resolver import resolve_tenant_id_sync

    return resolve_tenant_id_sync(phone_number_id)


@router.post("/whatsapp")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks, x_hub_signature_256: str | None = Header(None)):
    raw_body = await request.body()

    if not _verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        phone_number_id = change["metadata"]["phone_number_id"]

        messages = change.get("messages")
        if not messages:
            # status updates (delivered/read) etc — ack and ignore
            return Response(status_code=200)

        msg = messages[0]
        from_number = msg["from"]
        msg_id = msg["id"]
        text_body = msg.get("text", {}).get("body", "") or f"[{msg.get('type', 'unsupported')} message]"

        tenant_id = _resolve_tenant_id(phone_number_id)

        # CRITICAL: schedule the LangGraph pipeline as a background task and
        # return 200 immediately so Meta doesn't retry the delivery.
        background_tasks.add_task(run_agent, tenant_id, from_number, msg_id, text_body)

    except (KeyError, IndexError) as e:
        logger.warning("Malformed webhook payload: %s", e)
        # still 200 — Meta will retry on non-200s, and malformed payloads won't fix themselves
        return Response(status_code=200)

    return Response(status_code=200)
