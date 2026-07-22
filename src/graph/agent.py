from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    load_context,
    generate_code,
    execute_code,
    finalize_answer,
    handle_error,
)
from graph.edges import (
    after_load_context,
    after_execute_code,
    after_finalize_answer,
)


def _build_graph() -> StateGraph:
    # Questions go straight from context loading to code generation — no
    # clarification step. The agent always attempts a direct answer (and this
    # also removes one LLM call per question).
    g = StateGraph(AgentState)
    g.add_node("load_context", load_context)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("finalize_answer", finalize_answer)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("load_context")
    g.add_conditional_edges("load_context", after_load_context,
        {"generate_code": "generate_code", "handle_error": "handle_error"})
    g.add_edge("generate_code", "execute_code")
    g.add_conditional_edges("execute_code", after_execute_code,
        {"generate_code": "generate_code", "finalize_answer": "finalize_answer", "handle_error": "handle_error"})
    g.add_conditional_edges("finalize_answer", after_finalize_answer,
        {"end": END, "handle_error": "handle_error"})
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
