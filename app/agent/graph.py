from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    AgentState,
    inspect_node,
    retrieve_node,
    synthesize_node,
    triage_node,
)


def build_triage_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("triage", triage_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("inspect", inspect_node)
    workflow.add_node("synthesize", synthesize_node)

    workflow.add_edge(START, "triage")
    workflow.add_edge("triage", "retrieve")
    workflow.add_edge("retrieve", "inspect")
    workflow.add_edge("inspect", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


triage_graph = build_triage_graph()


async def run_triage_agent(
    fingerprint: str,
    service_name: str,
    environment: str,
    raw_log: str,
) -> dict:
    initial_state: AgentState = {
        "fingerprint": fingerprint,
        "service_name": service_name,
        "environment": environment,
        "raw_log": raw_log,
        "triage": {},
        "retrieved_chunks": [],
        "file_context": "",
        "git_history": "",
        "report": {},
    }
    final_state = await triage_graph.ainvoke(initial_state)
    return final_state["report"]