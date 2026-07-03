"""
The four pipeline nodes described in Task 3.
"""
import json
import re

from app.database import messages_col, sessions_col, tenants_col
from app.graph.state import AgentState
from app.models import (
    MediaAttachment,
    MessageDirection,
    MessageLog,
    SessionStatus,
    utcnow,
)
from app.whatsapp_client import WhatsAppClient

# ---------------------------------------------------------------------
# 1. Acknowledge Node
# ---------------------------------------------------------------------
async def acknowledge_node(state: AgentState) -> AgentState:
    wa = WhatsAppClient(state.get("whatsapp_phone_number_id"))

    # Fire off read receipt + typing indicator immediately
    await wa.mark_as_read(state["whatsapp_message_id"])
    await wa.start_typing(state["whatsapp_message_id"])

    # Persist inbound message + mark session PENDING_RESPONSE
    await messages_col().insert_one(
        MessageLog(
            tenant_id=state["tenant_id"],
            phone_number=state["phone_number"],
            direction=MessageDirection.INBOUND,
            sender="customer",
            text_content=state["inbound_text"],
            whatsapp_message_id=state["whatsapp_message_id"],
        ).model_dump()
    )

    await sessions_col().update_one(
        {"tenant_id": state["tenant_id"], "phone_number": state["phone_number"]},
        {
            "$set": {
                "status": SessionStatus.AGENT_RESPONDING.value,
                "is_typing": True,
                "last_message_at": utcnow(),
            },
            "$setOnInsert": {"context_variables": {}, "created_at": utcnow()},
        },
        upsert=True,
    )
    return state


# ---------------------------------------------------------------------
# 2. Context Retriever Node
# ---------------------------------------------------------------------
async def context_retriever_node(state: AgentState) -> AgentState:
    tenant = await tenants_col().find_one({"tenant_id": state["tenant_id"]})
    if not tenant:
        raise ValueError(f"Unknown tenant: {state['tenant_id']}")

    cursor = (
        messages_col()
        .find({"tenant_id": state["tenant_id"], "phone_number": state["phone_number"]})
        .sort("timestamp", -1)
        .limit(5)
    )
    recent = [doc async for doc in cursor]
    recent.reverse()  # chronological order

    state["tenant_prompt"] = tenant["prompt_directions"]
    state["media_library"] = tenant.get("media_library", [])
    state["whatsapp_phone_number_id"] = tenant.get("whatsapp_phone_number_id")
    state["history"] = [
        {"sender": m["sender"], "text": m.get("text_content") or ""} for m in recent
    ]
    return state


# ---------------------------------------------------------------------
# 3. LLM Reasoning Node
# ---------------------------------------------------------------------
TOOL_SCHEMA = [
    {
        "name": "reply",
        "description": "Send a reply to the customer over WhatsApp. Choose 'text' for a plain "
        "message, or 'image'/'document' when the customer's request matches an entry "
        "in the tenant's media library (e.g. they asked for a catalog, brochure, "
        "photo, invoice, diagram, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "response_type": {"type": "string", "enum": ["text", "image", "document"]},
                "response_text": {
                    "type": "string",
                    "description": "The message body / caption to send. Always required.",
                },
                "media_keyword": {
                    "type": "string",
                    "description": "If response_type is image/document, the exact keyword "
                    "from the tenant's media library to attach. Omit for text.",
                },
                "needs_human": {
                    "type": "boolean",
                    "description": "True if the customer sounds frustrated/angry and a human "
                    "agent should take over.",
                },
            },
            "required": ["response_type", "response_text", "needs_human"],
        },
    }
]

# ------------------------------------------------------------------
# Hardcoded shortcut keyword sets
# ------------------------------------------------------------------
GREETING_WORDS = {"hi", "hello", "hey", "hii", "heyy", "helo", "hola", "hlo"}
CONFIRM_WORDS = {"yes", "yeah", "yep", "confirm", "confirmed"}
NOT_FOUND_PHRASES = {"item not found", "not found", "item not available"}

ASK_PHONE_MSG = "please share your phone number to confirm the booking"


def _words(text: str) -> set:
    return set(re.findall(r"\b\w+\b", text.strip().lower()))


def _looks_like_phone_number(text: str) -> bool:
    """True if the message is mostly digits and a plausible phone length."""
    digits = re.sub(r"\D", "", text)
    return 7 <= len(digits) <= 15


async def llm_reasoning_node(state: AgentState) -> AgentState:
    from app.llm import call_llm_with_tool  # local import avoids circulars at module load

    normalized = state["inbound_text"].strip().lower()
    msg_words = _words(normalized)

    # Was the bot's last message the "please share your phone number" prompt?
    last_bot_msg = next(
        (h["text"] for h in reversed(state["history"]) if h["sender"] == "bot"), ""
    )
    awaiting_phone_number = ASK_PHONE_MSG in (last_bot_msg or "").strip().lower()

    # ------------------------------------------------------------------
    # Quick hardcoded shortcuts (skip the LLM call entirely for these)
    # ------------------------------------------------------------------

    # 0) We just asked for a phone number and this message looks like one
    #    -> save it and confirm.
    if awaiting_phone_number and _looks_like_phone_number(state["inbound_text"]):
        customer_phone = re.sub(r"\D", "", state["inbound_text"])
        await sessions_col().update_one(
            {"tenant_id": state["tenant_id"], "phone_number": state["phone_number"]},
            {"$set": {"context_variables.customer_phone": customer_phone}},
        )
        state["response_type"] = "text"
        state["response_text"] = (
            "number saved. confirmation message will be sent in 24 hrs"
        )
        state["sentiment_needs_human"] = False
        return state

    # 1) Greeting -> welcome message
    if msg_words & GREETING_WORDS:
        state["response_type"] = "text"
        state["response_text"] = "hello, welcome!"
        state["sentiment_needs_human"] = False
        return state

    # 2) "item not found" -> apology
    if any(phrase in normalized for phrase in NOT_FOUND_PHRASES):
        state["response_type"] = "text"
        state["response_text"] = "new items will be added soon"
        state["sentiment_needs_human"] = False
        return state

    # 3) "yes" / confirmation -> ask for phone number before confirming
    if msg_words & CONFIRM_WORDS:
        state["response_type"] = "text"
        state["response_text"] = ASK_PHONE_MSG
        state["sentiment_needs_human"] = False
        return state

    # 4) "available" -> list media library items with confirm instructions
    if "available" in normalized:
        item_names = [m.get("label") or m["keyword"] for m in state["media_library"]]
        if item_names:
            names_list = ", ".join(item_names)
            reply_text = (
                f"yes: {names_list}\n\n"
                "to confirm click item name and yes"
            )
        else:
            reply_text = "no items configured yet"
        state["response_type"] = "text"
        state["response_text"] = reply_text
        state["sentiment_needs_human"] = False
        return state
    # ------------------------------------------------------------------

    media_desc = "\n".join(
        f"- keyword='{m['keyword']}' -> {m['url']} ({m['mime_type']})" for m in state["media_library"]
    )
    history_desc = "\n".join(f"{h['sender']}: {h['text']}" for h in state["history"])

    system_prompt = (
        f"{state['tenant_prompt']}\n\n"
        "You are a WhatsApp sales/support agent for this business. You have access to a "
        "media library of assets you can attach when relevant:\n"
        f"{media_desc or '(no media configured)'}\n\n"
        "Recent conversation history:\n"
        f"{history_desc or '(no prior messages)'}\n\n"
        "Respond to the customer's latest message by calling the `reply` tool. "
        "Only choose image/document response_type if the customer is clearly asking for "
        "visual/document assets that match a media_keyword above."
    )

    tool_input = await call_llm_with_tool(
        system_prompt=system_prompt,
        user_message=state["inbound_text"],
        tools=TOOL_SCHEMA,
    )

    state["response_type"] = tool_input.get("response_type", "text")
    state["response_text"] = tool_input.get("response_text", "")
    state["sentiment_needs_human"] = bool(tool_input.get("needs_human", False))

    media_keyword = tool_input.get("media_keyword")
    if state["response_type"] in ("image", "document") and media_keyword:
        match = next((m for m in state["media_library"] if m["keyword"] == media_keyword), None)
        if match:
            state["media_url"] = match["url"]
            state["media_mime_type"] = match["mime_type"]
            state["media_filename"] = match.get("label", media_keyword) + (
                ".pdf" if match["mime_type"] == "application/pdf" else ""
            )
        else:
            # keyword hallucinated / not found -> fall back to text
            state["response_type"] = "text"
    return state


# ---------------------------------------------------------------------
# 4. Dispatcher Node
# ---------------------------------------------------------------------
async def dispatcher_node(state: AgentState) -> AgentState:
    wa = WhatsAppClient(state.get("whatsapp_phone_number_id"))

    if state["sentiment_needs_human"]:
        new_status = SessionStatus.NEEDS_HUMAN
    else:
        new_status = SessionStatus.RESOLVED

    media_attachment = None
    if state["response_type"] == "image":
        result = await wa.send_image(state["phone_number"], state["media_url"], caption=state["response_text"])
        media_attachment = MediaAttachment(url=state["media_url"], mime_type=state["media_mime_type"])
    elif state["response_type"] == "document":
        result = await wa.send_document(
            state["phone_number"], state["media_url"], state["media_filename"], caption=state["response_text"]
        )
        media_attachment = MediaAttachment(
            url=state["media_url"], mime_type=state["media_mime_type"], filename=state["media_filename"]
        )
    else:
        result = await wa.send_text(state["phone_number"], state["response_text"])

    await messages_col().insert_one(
        MessageLog(
            tenant_id=state["tenant_id"],
            phone_number=state["phone_number"],
            direction=MessageDirection.OUTBOUND,
            sender="bot",
            text_content=state["response_text"],
            media=media_attachment,
            whatsapp_message_id=result.get("messages", [{}])[0].get("id"),
        ).model_dump()
    )

    # sending the reply extinguishes the typing indicator on WhatsApp's side;
    # mirror that in our own session state for the dashboard
    await sessions_col().update_one(
        {"tenant_id": state["tenant_id"], "phone_number": state["phone_number"]},
        {"$set": {"status": new_status.value, "is_typing": False, "last_message_at": utcnow()}},
    )
    return state