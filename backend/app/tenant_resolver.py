"""
Small in-memory cache mapping a WABA phone_number_id -> tenant_id, refreshed
at startup and after tenant CRUD. Keeps the webhook's hot path synchronous
and fast (no DB round trip needed just to route the message).
"""
from app.config import get_settings

settings = get_settings()

_phone_to_tenant: dict[str, str] = {}


def set_mapping(mapping: dict[str, str]):
    global _phone_to_tenant
    _phone_to_tenant = mapping


def resolve_tenant_id_sync(phone_number_id: str) -> str:
    return _phone_to_tenant.get(phone_number_id, _phone_to_tenant.get("default", "tenant-a"))


async def refresh_mapping():
    from app.database import tenants_col

    mapping = {}
    async for t in tenants_col().find({}):
        if t.get("whatsapp_phone_number_id"):
            mapping[t["whatsapp_phone_number_id"]] = t["tenant_id"]
    if settings.META_PHONE_NUMBER_ID:
        # sandbox: single shared number, default to first tenant unless mapped
        mapping.setdefault(settings.META_PHONE_NUMBER_ID, next(iter(mapping.values()), "tenant-a"))
    set_mapping(mapping)
