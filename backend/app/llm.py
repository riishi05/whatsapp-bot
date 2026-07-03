"""
Minimal LLM wrapper that forces a tool call so the LangGraph Reasoning Node
gets structured output (response_type / response_text / media_keyword /
needs_human) regardless of which provider is configured.
"""
import json

from app.config import get_settings

settings = get_settings()


async def call_llm_with_tool(system_prompt: str, user_message: str, tools: list[dict]) -> dict:
    if settings.LLM_PROVIDER == "openai":
        return await _call_openai(system_prompt, user_message, tools)
    return await _call_anthropic(system_prompt, user_message, tools)


async def _call_anthropic(system_prompt: str, user_message: str, tools: list[dict]) -> dict:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    resp = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1024,
        system=system_prompt,
        tools=tools,
        tool_choice={"type": "tool", "name": "reply"},
        messages=[{"role": "user", "content": user_message}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"response_type": "text", "response_text": "Sorry, something went wrong.", "needs_human": False}


async def _call_openai(system_prompt: str, user_message: str, tools: list[dict]) -> dict:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    oai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]
    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        tools=oai_tools,
        tool_choice={"type": "function", "function": {"name": "reply"}},
    )
    call = resp.choices[0].message.tool_calls[0]
    return json.loads(call.function.arguments)
