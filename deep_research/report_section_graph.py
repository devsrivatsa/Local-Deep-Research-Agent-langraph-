from langgraph.graph import StateGraph, START, END
from state import SectionState
from research_steps import (
    generate_queries,
    search_web,
)

graph_builder = StateGraph(SectionState, output=SectionOutputState)

graph_builder.add_node("genrrate_queries", generate_queries)
graph_builder.add_node("search_web", search_web)

#edges
graph_builder.add_edge(START, "genrrate_queries")
graph_builder.add_edge("genrrate_queries", "search_web")


graph = graph_builder.compile()