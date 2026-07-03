"""
Task 5: Broadcast Campaign Drawer backend.
Lets an admin pick a cohort of phone numbers + a pre-approved WhatsApp
template and fire it to all of them.
"""
from pydantic import BaseModel

from fastapi import APIRouter

from app.database import sessions_col
from app.whatsapp_client import WhatsAppClient

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


class BroadcastRequest(BaseModel):
    tenant_id: str
    template_name: str
    language_code: str = "en_US"
    # cohort: explicit numbers, or "all" for every session under this tenant
    phone_numbers: list[str] | None = None


@router.post("")
async def send_broadcast(req: BroadcastRequest):
    if req.phone_numbers:
        targets = req.phone_numbers
    else:
        sessions = await sessions_col().find({"tenant_id": req.tenant_id}, {"phone_number": 1}).to_list(1000)
        targets = [s["phone_number"] for s in sessions]

    wa = WhatsAppClient()
    results = []
    for number in targets:
        try:
            res = await wa.send_template(number, req.template_name, req.language_code)
            results.append({"phone_number": number, "status": "sent", "id": res.get("messages", [{}])[0].get("id")})
        except Exception as e:  # noqa: BLE001 - report per-recipient failures without aborting the batch
            results.append({"phone_number": number, "status": "failed", "error": str(e)})

    return {"sent": sum(1 for r in results if r["status"] == "sent"), "results": results}
