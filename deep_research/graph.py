from langgraph.graph import StateGraph, START, END
from state import ReportState, ReportStateInput, ReportStateOutput
from configuration import Configuration
from reporting import (
    generate_report_plan, 
    human_feedback,
    gather_completed_sections,
    initiate_final_section_writing,
    write_final_sections,
    compile_final_report
)
from section_builder_graph import graph as section_builder

builder = StateGraph(
    ReportState,
    input=ReportStateInput,
    output=ReportStateOutput,
    config_schema=Configuration
)

builder.add_node("generate_report_plan", generate_report_plan)
builder.add_node("human_feedback", human_feedback)
builder.add_node("build_section_with_web_search", section_builder)
builder.add_node("gather_completed_sections", gather_completed_sections)
builder.add_node("write_final_sections", write_final_sections)
builder.add_node("compile_final_report", compile_final_report)

builder.add_edge(START, "generate_report_plan")
builder.add_edge("generate_report_plan", "human_feedback")
builder.add_edge("build_section_with_web_search", "gather_completed_sections")
builder.add_conditional_edges("gather_completed_sections", initiate_final_section_writing, ["write_final_sections"])
builder.add_edge("write_final_sections", "compile_final_report")
builder.add_edge("compile_final_report", END)

graph = builder.compile()