from langgraph.graph import StateGraph, START, END
from state import ReportState, ReportStateInput, ReportStateOutput
from configuration import Configuration

builder = StateGraph(
    ReportState,
    input=ReportStateInput,
    output=ReportStateOutput,
    config_schema=Configuration
)

builder.add_node("generate_report_plan", generate_report_plan)