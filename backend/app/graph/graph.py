import uuid

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph import edges, nodes
from app.graph.dependencies import GraphDependencies
from app.graph.state import GraphState

type _StateBuilder = StateGraph[GraphState, None, GraphState, GraphState]


def turn_input(session_id: uuid.UUID, message: str) -> GraphState:
    """The `input` argument for graph.ainvoke() for one turn of conversation."""
    return {"session_id": str(session_id), "messages": [HumanMessage(content=message)]}


def config_for(session_id: uuid.UUID) -> RunnableConfig:
    """The `config` argument for graph.ainvoke() -- thread_id is the session
    ID, so the checkpointer's conversation memory is scoped per session."""
    return {"configurable": {"thread_id": str(session_id)}}


def _add_node(builder: _StateBuilder, name: str, node: nodes.Node) -> None:
    # mypy can't resolve add_node's method-level generic NodeInputT through
    # our `Node` Callable type alias -- structurally correct at runtime
    # (verified: every node below runs and is exercised by tests), so this
    # centralizes one suppression instead of repeating type: ignore at each
    # of the 14 add_node call sites.
    builder.add_node(name, node)  # type: ignore[call-overload]


def build_graph(
    deps: GraphDependencies, *, checkpointer: BaseCheckpointSaver[str] | None = None
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    """Assembles the IlliniAssist AI conversation graph.

    Node order and names follow the spec's canonical list (Load Session ->
    Check Student Profile -> Intent Detection -> Question Classification ->
    Metadata Filter -> Retriever -> Hybrid Search -> Re-ranker -> Context
    Builder -> Generate Response -> Citation Generator -> Save Conversation
    State) with four deliberate deviations, each explained where it's
    built: "Retriever" and "Hybrid Search" are merged into one `retrieve`
    node (Phase 4's HybridRetriever already performs both as one operation),
    a `clarification` node is added (not in the spec's literal list, but
    implied by "the chatbot may ask about student type" and required for
    genuine conditional routing rather than a single straight-line path),
    an `assess_retrieval_sufficiency` node sits between context_builder
    and generate_response with a conditional edge back to `retrieve` --
    the graph's first (and only) cycle, gated by
    Settings.agentic_retrieval_enabled and always bounded by
    Settings.agentic_retrieval_max_attempts (see
    edges.route_after_sufficiency_check), never relying on LangGraph's
    recursion_limit as the actual termination mechanism -- and a
    `decompose_query` node sits between question_classification and
    metadata_filter, splitting a genuinely multi-part question into
    independent sub-queries `retrieve` fans out over and merges (gated by
    Settings.query_decomposition_enabled, always a no-op single-item list
    when off).
    """
    builder: _StateBuilder = StateGraph(GraphState)

    _add_node(builder, "load_session", nodes.make_load_session_node(deps))
    _add_node(builder, "check_student_profile", nodes.make_check_student_profile_node(deps))
    _add_node(builder, "intent_detection", nodes.make_intent_detection_node())
    _add_node(builder, "question_classification", nodes.make_question_classification_node(deps))
    _add_node(builder, "clarification", nodes.make_clarification_node())
    _add_node(builder, "decompose_query", nodes.make_decompose_query_node(deps))
    _add_node(builder, "metadata_filter", nodes.make_metadata_filter_node())
    _add_node(builder, "retrieve", nodes.make_retrieve_node(deps))
    _add_node(builder, "re_ranker", nodes.make_reranker_node(deps))
    _add_node(builder, "context_builder", nodes.make_context_builder_node())
    _add_node(
        builder,
        "assess_retrieval_sufficiency",
        nodes.make_assess_retrieval_sufficiency_node(deps),
    )
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
        {"clarify": "clarification", "continue": "decompose_query"},
    )
    builder.add_edge("clarification", "save_conversation_state")
    builder.add_edge("decompose_query", "metadata_filter")
    builder.add_edge("metadata_filter", "retrieve")
    builder.add_edge("retrieve", "re_ranker")
    builder.add_edge("re_ranker", "context_builder")
    builder.add_edge("context_builder", "assess_retrieval_sufficiency")
    builder.add_conditional_edges(
        "assess_retrieval_sufficiency",
        edges.route_after_sufficiency_check,
        {"retry": "retrieve", "continue": "generate_response"},
    )
    builder.add_edge("generate_response", "citation_generator")
    builder.add_edge("citation_generator", "save_conversation_state")
    builder.add_edge("save_conversation_state", END)

    return builder.compile(checkpointer=checkpointer)
