"""
Async MongoDB connection (Motor) + collection accessors.
Multi-tenancy is enforced at the query level: every collection except
`tenants` carries a `tenant_id` field that MUST be filtered on for every
read/write, so tenants never leak into each other's data.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

settings = get_settings()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.MONGO_DB_NAME]
    return _db


# Collection shortcuts -------------------------------------------------
def tenants_col():
    return get_db()["tenants"]


def sessions_col():
    return get_db()["chat_sessions"]


def messages_col():
    return get_db()["message_logs"]


async def ensure_indexes():
    """Call once at startup to create indexes (safe to call repeatedly)."""
    await tenants_col().create_index("tenant_id", unique=True)
    await sessions_col().create_index([("tenant_id", 1), ("phone_number", 1)], unique=True)
    await messages_col().create_index([("tenant_id", 1), ("phone_number", 1), ("timestamp", 1)])
