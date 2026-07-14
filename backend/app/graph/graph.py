from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph import edges, nodes
from app.graph.dependencies import GraphDependencies
from app.graph.state import GraphState

type _StateBuilder = StateGraph[GraphState, None, GraphState, GraphState]


def _add_node(builder: _StateBuilder, name: str, node: nodes.Node) -> None:
    # mypy can't resolve add_node's method-level generic NodeInputT through
    # our `Node` Callable type alias -- structurally correct at runtime
    # (verified: every node below runs and is exercised by tests), so this
    # centralizes one suppression instead of repeating type: ignore at each
    # of the 12 add_node call sites.
    builder.add_node(name, node)  # type: ignore[call-overload]


def build_graph(
    deps: GraphDependencies, *, checkpointer: BaseCheckpointSaver[str] | None = None
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    """Assembles the IlliniGuide AI conversation graph.

    Node order and names follow the spec's canonical list (Load Session ->
    Check Student Profile -> Intent Detection -> Question Classification ->
    Metadata Filter -> Retriever -> Hybrid Search -> Re-ranker -> Context
    Builder -> Generate Response -> Citation Generator -> Save Conversation
    State) with two deliberate deviations, both explained where they're
    built: "Retriever" and "Hybrid Search" are merged into one `retrieve`
    node (Phase 4's HybridRetriever already performs both as one operation),
    and a `clarification` node is added (not in the spec's literal list, but
    implied by "the chatbot may ask about student type" and required for
    genuine conditional routing rather than a single straight-line path).
    """
    builder: _StateBuilder = StateGraph(GraphState)

    _add_node(builder, "load_session", nodes.make_load_session_node(deps))
    _add_node(builder, "check_student_profile", nodes.make_check_student_profile_node())
    _add_node(builder, "intent_detection", nodes.make_intent_detection_node())
    _add_node(
        builder, "question_classification", nodes.make_question_classification_node(deps)
    )
    _add_node(builder, "clarification", nodes.make_clarification_node())
    _add_node(builder, "metadata_filter", nodes.make_metadata_filter_node())
    _add_node(builder, "retrieve", nodes.make_retrieve_node(deps))
    _add_node(builder, "re_ranker", nodes.make_reranker_node(deps))
    _add_node(builder, "context_builder", nodes.make_context_builder_node())
    _add_node(builder, "generate_response", nodes.make_generate_response_node(deps))
    _add_node(builder, "citation_generator", nodes.make_citation_generator_node())
    _add_node(builder, "save_conversation_state", nodes.make_save_conversation_state_node())

    builder.add_edge(START, "load_session")
    builder.add_edge("load_session", "check_student_profile")
    builder.add_conditional_edges(
        "check_student_profile",
        edges.route_after_profile_check,
        {"clarify": "clarification", "continue": "intent_detection"},
    )
    builder.add_conditional_edges(
        "intent_detection",
        edges.route_after_intent,
        {"greeting": "generate_response", "question": "question_classification"},
    )
    builder.add_conditional_edges(
        "question_classification",
        edges.route_after_classification,
        {"clarify": "clarification", "continue": "metadata_filter"},
    )
    builder.add_edge("clarification", "save_conversation_state")
    builder.add_edge("metadata_filter", "retrieve")
    builder.add_edge("retrieve", "re_ranker")
    builder.add_edge("re_ranker", "context_builder")
    builder.add_edge("context_builder", "generate_response")
    builder.add_edge("generate_response", "citation_generator")
    builder.add_edge("citation_generator", "save_conversation_state")
    builder.add_edge("save_conversation_state", END)

    return builder.compile(checkpointer=checkpointer)
