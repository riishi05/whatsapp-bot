"""
Read-only(ish) API consumed by the frontend monitoring dashboard.
"""
from fastapi import APIRouter, HTTPException

from app.database import messages_col, sessions_col, tenants_col
from app.models import MediaLibraryEntry, Tenant

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/tenants")
async def list_tenants():
    tenants = await tenants_col().find({}, {"_id": 0}).to_list(length=100)
    return tenants


@router.post("/tenants")
async def create_tenant(tenant: Tenant):
    existing = await tenants_col().find_one({"tenant_id": tenant.tenant_id})
    if existing:
        raise HTTPException(status_code=409, detail="tenant_id already exists")
    await tenants_col().insert_one(tenant.model_dump())

    from app.tenant_resolver import refresh_mapping

    await refresh_mapping()
    return {"ok": True}


@router.get("/tenants/{tenant_id}/sessions")
async def list_sessions(tenant_id: str):
    """Active phone numbers conversing with the bot for this tenant."""
    sessions = (
        await sessions_col()
        .find({"tenant_id": tenant_id}, {"_id": 0})
        .sort("last_message_at", -1)
        .to_list(length=200)
    )
    return sessions


@router.get("/tenants/{tenant_id}/sessions/{phone_number}/messages")
async def get_thread(tenant_id: str, phone_number: str):
    """Full stylized chat thread for one customer."""
    msgs = (
        await messages_col()
        .find({"tenant_id": tenant_id, "phone_number": phone_number}, {"_id": 0})
        .sort("timestamp", 1)
        .to_list(length=500)
    )
    return msgs
