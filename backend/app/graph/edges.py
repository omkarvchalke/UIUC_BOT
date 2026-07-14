from typing import Literal

from app.graph.state import GraphState

ProfileRoute = Literal["clarify", "continue"]
IntentRoute = Literal["greeting", "question"]
ClassificationRoute = Literal["clarify", "continue"]


def route_after_profile_check(state: GraphState) -> ProfileRoute:
    return "clarify" if state.get("needs_clarification") else "continue"


def route_after_intent(state: GraphState) -> IntentRoute:
    return "greeting" if state.get("intent") == "greeting" else "question"


def route_after_classification(state: GraphState) -> ClassificationRoute:
    return "clarify" if state.get("needs_clarification") else "continue"
