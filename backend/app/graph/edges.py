from typing import Literal

from app.core.config import get_settings
from app.graph.state import GraphState

ProfileRoute = Literal["clarify", "continue"]
IntentRoute = Literal["greeting", "question"]
ClassificationRoute = Literal["clarify", "continue"]
RetrievalSufficiencyRoute = Literal["retry", "continue"]


def route_after_profile_check(state: GraphState) -> ProfileRoute:
    return "clarify" if state.get("needs_clarification") else "continue"


def route_after_intent(state: GraphState) -> IntentRoute:
    return "greeting" if state.get("intent") == "greeting" else "question"


def route_after_classification(state: GraphState) -> ClassificationRoute:
    return "clarify" if state.get("needs_clarification") else "continue"


def route_after_sufficiency_check(state: GraphState) -> RetrievalSufficiencyRoute:
    # Default sufficient=True: AlwaysSufficientChecker always sets this
    # explicitly, but the default here matters too if this node is ever
    # reached without having run (defensive, shouldn't happen given the
    # graph's wiring).
    if state.get("retrieval_sufficient", True):
        return "continue"
    # Always terminates even if the checker keeps saying "insufficient"
    # forever (a misbehaving LLM response must never dead-end a turn):
    # give up and proceed to generation with whatever context exists once
    # the attempt budget is spent, rather than looping indefinitely and
    # relying on LangGraph's recursion_limit as the real backstop.
    if state.get("retrieval_attempt", 0) >= get_settings().agentic_retrieval_max_attempts:
        return "continue"
    return "retry"
