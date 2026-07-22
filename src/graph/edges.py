from config.settings import get_settings
from graph.state import AgentState


def after_load_context(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "generate_code"


def after_execute_code(state: AgentState) -> str:
    exec_result = state.get("exec_result") or {}
    if exec_result.get("error"):
        max_attempts = get_settings().max_code_generation_attempts
        if state.get("attempts", 0) < max_attempts:
            return "generate_code"
        return "handle_error"
    return "finalize_answer"


def after_finalize_answer(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "end"
