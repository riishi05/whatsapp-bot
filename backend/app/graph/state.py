"""
Shared state object threaded through every LangGraph node.
"""
from typing import Optional, TypedDict


class AgentState(TypedDict, total=False):
    # inbound payload
    tenant_id: str
    phone_number: str
    whatsapp_message_id: str
    inbound_text: str

    # loaded by Context Retriever Node
    tenant_prompt: str
    media_library: list[dict]  # [{keyword, url, mime_type, label}]
    history: list[dict]  # last 5 messages [{sender, text}]

    # produced by LLM Reasoning Node
    response_type: str  # "text" | "image" | "document"
    response_text: Optional[str]
    media_url: Optional[str]
    media_filename: Optional[str]
    media_mime_type: Optional[str]
    sentiment_needs_human: bool

    # bookkeeping
    whatsapp_phone_number_id: Optional[str]
