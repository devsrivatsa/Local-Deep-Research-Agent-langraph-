from utils import get_config_value, get_search_params
from state import ReportState, Queries, Sections
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model
from prompts import report_planner_query_writer_instructions, report_planner_instructions

async def generate_report_plan(state: ReportState, config: RunnableConfig):
    """Generate the inital report plan with sessions.
    This node:
    1. Gets the configuration for the report structure and search parameters
    2. Generates search queries to gather context for planning
    3. Performs web searches using those queries
    4. Uses an LLM to generate a structured report plan
    
    Args:
        state: Current state with report details
        config: Configuration for report generation
        
    Returns:
        Updated state with generated sections
    """
    topic = state["topic"]
    feedback = state.get("feedback_on_report_plan", None)
    configuration = config.from_runnable_config(config)
    report_structure = configuration.report_structure
    number_of_queries = configuration.number_of_queries
    search_api = get_config_value(configuration.search_api, "google")
    search_api_config = get_config_value(configuration.search_api_config, {})
    params_to_pass = get_search_params(search_api, search_api_config)

    if isinstance(report_structure, dict):
        report_structure = str(report_structure)
    
    writer_provider = get_config_value(configuration.writer_provider)
    writer_model_name = get_config_value(configuration.writer_model)
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider)
    structured_llm = writer_model.with_structured_output(Queries)
    
    # Format the system instructions for the query writer
    system_instructions_query = report_planner_query_writer_instructions.format(
        topic=topic,
        report_organization=report_structure,
        number_of_queries=number_of_queries
    )

    # Generate the queries
    structured_llm = writer_model.with_structured_output(Queries)
    results = structured_llm.invoke([
        SystemMessage(content=system_instructions_query), 
        HumanMessage(content="Generate search queries that will help with planning the sections of the report.")
    ])

    query_list = [q.search_query for q in results.queries]

    source_str = await select_and_execute_search(search_api, query_list, params_to_pass)

    system_instructions_sections = report_planner_instructions.format(
        topic=topic, 
        report_organization=report_structure, 
        context=source_str, 
        feedback=feedback
    )

    planner_provider = get_config_value(configuration.planner_provider)
    planner_model = get_config_value(configuration.planner_model)

    planner_message = """Generate the section of the report. Your response must include a 'sections' field containing a list of sections. Each section
    must have: name, description, plan, research, and content fields."""

    if planner_model == "claude-3.7-sonnel-latest":
        #allocate a thinking budget
        planner_llm = init_chat_model(
            model=planner_model, model_provider=planner_provider,
            max_tokens=20_000,
            temperature=0.0,
            thinking={"type": "enabled", "budget_tokens": 16_000}
        )
    else:
        planner_llm = init_chat_model(
            model=planner_model, model_provider=planner_provider
        )

    structured_llm = planner_llm.with_structured_output(Sections)
    report_sections = planner_llm.invoke([
        SystemMessage(content=system_instructions_sections),
        HumanMessage(content=planner_message)
    ])

    sections = report_sections.sections
    return {"sections": sections}