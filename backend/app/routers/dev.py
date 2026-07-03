"""
DEV/TEST ONLY: simulate an inbound WhatsApp message and run it through the
exact same LangGraph pipeline the real webhook uses — without needing a
working Meta sandbox connection. Useful for local demoing/testing the
Acknowledge -> ContextRetriever -> LLMReasoning -> Dispatcher flow and
seeing results show up live on the dashboard.

NOT wired to any Meta signature checks since it never touches Meta at all.
Do not expose this router in a production deployment.
"""
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.graph.graph import run_agent

router = APIRouter(prefix="/api/dev", tags=["dev"])


class SimulateMessageRequest(BaseModel):
    tenant_id: str
    phone_number: str  # any string works, e.g. "test-user-1" — doesn't need to be a real WA number
    text: str


@router.post("/simulate-message")
async def simulate_message(req: SimulateMessageRequest):
    fake_message_id = f"dev-{uuid.uuid4().hex[:12]}"
    result = await run_agent(
        tenant_id=req.tenant_id,
        phone_number=req.phone_number,
        whatsapp_message_id=fake_message_id,
        inbound_text=req.text,
    )
    return {
        "ok": True,
        "response_type": result.get("response_type"),
        "response_text": result.get("response_text"),
    }
