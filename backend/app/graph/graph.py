"""
Wires the 4 nodes into a linear StateGraph:

  Acknowledge -> ContextRetriever -> LLMReasoning -> Dispatcher -> END

Compiled once at import time and reused (async invocation per message).
"""
from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    acknowledge_node,
    context_retriever_node,
    dispatcher_node,
    llm_reasoning_node,
)
from app.graph.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("acknowledge", acknowledge_node)
    graph.add_node("context_retriever", context_retriever_node)
    graph.add_node("llm_reasoning", llm_reasoning_node)
    graph.add_node("dispatcher", dispatcher_node)

    graph.set_entry_point("acknowledge")
    graph.add_edge("acknowledge", "context_retriever")
    graph.add_edge("context_retriever", "llm_reasoning")
    graph.add_edge("llm_reasoning", "dispatcher")
    graph.add_edge("dispatcher", END)

    return graph.compile()


agent_graph = build_graph()


async def run_agent(tenant_id: str, phone_number: str, whatsapp_message_id: str, inbound_text: str):
    initial_state: AgentState = {
        "tenant_id": tenant_id,
        "phone_number": phone_number,
        "whatsapp_message_id": whatsapp_message_id,
        "inbound_text": inbound_text,
    }
    return await agent_graph.ainvoke(initial_state)
