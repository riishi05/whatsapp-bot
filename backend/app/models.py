"""
Pydantic schemas mirroring the Mongo document shapes.
These are used for request/response validation and for type-safe reads
from the DB layer. Mongo itself stays schemaless — validation happens here.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------
# Task 1: Tenant (Company)
# ---------------------------------------------------------------------
class MediaLibraryEntry(BaseModel):
    keyword: str  # e.g. "catalog", "sofa"
    url: str
    mime_type: str  # e.g. "application/pdf", "image/png"
    label: Optional[str] = None  # human friendly name e.g. "Product Catalog"


class Tenant(BaseModel):
    tenant_id: str  # unique slug, e.g. "luxury-furniture"
    name: str
    prompt_directions: str  # system instructions for the LLM
    media_library: list[MediaLibraryEntry] = Field(default_factory=list)
    whatsapp_phone_number_id: Optional[str] = None  # allows per-tenant WABA numbers
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------
# Task 1: Customer Interaction (Chat Session)
# ---------------------------------------------------------------------
class SessionStatus(str, Enum):
    WAITING_FOR_BOT = "WAITING_FOR_BOT"
    AGENT_RESPONDING = "AGENT_RESPONDING"
    RESOLVED = "RESOLVED"
    NEEDS_HUMAN = "NEEDS_HUMAN"  # bonus: sentiment/frustration handover


class ChatSession(BaseModel):
    tenant_id: str
    phone_number: str
    status: SessionStatus = SessionStatus.WAITING_FOR_BOT
    context_variables: dict = Field(default_factory=dict)
    is_typing: bool = False
    last_message_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------
# Task 1: Message Audit Log
# ---------------------------------------------------------------------
class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MediaAttachment(BaseModel):
    url: str
    mime_type: str
    filename: Optional[str] = None


class MessageLog(BaseModel):
    tenant_id: str
    phone_number: str
    direction: MessageDirection
    sender: str  # "customer" | "bot" | "agent"
    text_content: Optional[str] = None
    media: Optional[MediaAttachment] = None
    whatsapp_message_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=utcnow)
