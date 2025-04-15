from utils import get_config_value, get_search_params
from state import (
    ReportState, 
    Queries, 
    Sections, 
    SectionState, 
    Feedback, 
    Section
)
from configuration import Configuration
from langgraph.types import Command, interrupt
from langgraph.constants import Send
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model
from prompts import (
    report_planner_query_writer_instructions, 
    report_planner_instructions, 
    section_writer_instructions, 
    section_writer_inputs, 
    section_grader_instructions,
    final_section_writer_instructions
)
from search.search_utils import select_and_execute_search
from typing import Literal
from langgraph.graph import END


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


def human_feedback(state: ReportState, config: RunnableConfig) -> Command[Literal["generate_report_plan", "build_section_with_web_search"]]:
    """Gets human feedback on the report plan and route it to the next appropriate node
    
    This node:
    1. Formats the current report plan for human review
    2. Gets the feedback via an interrupt
    3. Routes to either:
        - generate_report_plan if the feedback is positive
        - build_section_with_web_search if any improvements are needed
    
    Args:
        state: Current state with report details
        config: Configuration for report generation
        
    Returns:
        Command to either generate a new plan or start section writing
    """

    topic = state["topic"]
    sections = state["sections"]
    sections_str = "\n\n".join([
        f"Section: {section.name}\n"
        f"Description: {section.description}\n"
        f"Research needed: {'Yes' if section.research else 'No'}\n"
        for section in sections
    ])

    interrupt_message = f"""Please provide feedback on the following report plan.
    \n\n{sections_str}\n
    \nDoes the report plan meet your needs?\nPass 'true' if it does, and to approve it.\nOr provide feedback on how it needs to be improved."""

    feedback = interrupt(interrupt_message)
    if isinstance(feedback, bool) and feedback is True:
        return Command(goto=[
            Send("build_section_with_web_search", {"topic": topic, "sections": sec, "search_iterations":0}) 
            for sec in sections if sec.research
        ])
    
    elif isinstance(feedback, str):
        return Command(goto="generate_report_plan", update={"feedback_on_report_plan": feedback})
    
    else:
        raise TypeError(f"Interrupt value of type {type(feedback)} is not supported")
    


def write_section(state: SectionState, config: RunnableConfig) -> Command:
    """Write a section of the report and evaluate if more research is needed.
    
    This node:
    1. Writes the section content using search results.
    2. Evaluates the quality of the section
    3. Either:
        - Completes the section if quality passes
        - Triggers more research if quality fails

    Args:
        state: Current state with section details
        config: Configuration for section writing
        
    Returns:
        Command to either search the web or complete the section
    """

    topic = state["topic"]
    section = state["section"]
    source_str = state["source_str"]

    configurable = Configuration.from_runnable_config(config)
    
    section_writer_inputs_formatted = section_writer_inputs.format(
        topic=topic,
        section_name=section.name,
        section_topic=section.description,
        context=source_str,
        section_content=section.content
    )

    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider)

    section_content = writer_model.invoke([
        SystemMessage(content=section_writer_instructions),
        HumanMessage(content=section_writer_inputs_formatted)
    ])

    section.content = section_content.content

    section_grader_message = ("Grade the report and consider follow-up questions for missing information.",
                              "If the grade is 'pass', return empty strings for any follow up queries", 
                              "If the grade is 'fail', provide specific search queries to gather missing information.")
    
    section_grader_instructions_formatted = section_grader_instructions.format(
        topic=topic,
        section_topic=section.description,
        section=section.content,
        number_of_follow_up_queries=configurable.number_of_follow_up_queries
    )

    planner_provider = get_config_value(configurable.planner_provider)
    planner_model = get_config_value(configurable.planner_model)

    if planner_model == "claude-3.7-sonnel-latest":
        reflection_model = init_chat_model(
            model=planner_model, model_provider=planner_provider,
            max_tokens=20_000,
            temperature=0.0,
            thinking={"type": "enabled", "budget_tokens": 16_000}
        ).with_structured_output(Feedback)
    else:
        reflection_model = init_chat_model(model=planner_model, model_provider=planner_provider).with_structured_output(Feedback)
    
    feedback = reflection_model.invoke([
        SystemMessage(content=section_grader_instructions_formatted), 
        HumanMessage(content=section_grader_message)])
    
    if feedback.grade == 'pass' or state['search_iterations'] >= configurable.max_search_depth:
        return Command(
            update={"completed_sections":[section]},
            goto=END
        )
    else:
        return Command(
            update={"search_iterations": feedback.follow_up_queries, "section": section},
            goto="search_web"
        )


def format_sections(sections: list[Section]) -> str:
    """Format the completed sections into a string"""
    formatted_string = ""
    for idx, section in enumerate(sections, 1):
        formatted_string += f"""
        {'='*60}
        Section {idx}: {section.name}
        {'-'*60}
        Description:
        {section.description}
        Requires research:
        {section.research}
        
        Content:
        {section.content if section.content else '[Not written yet]'}
        """

    return formatted_string

def gather_completed_sections(state: ReportState):
    """Format the completed sections as context for writing final sections.
    
    This node takes all completed research sections and formats them into a single context
    string for writing summary sections.
    
    Args:
        state: current state with completed sections
    
    Returns:
        Dict with formatted sections as context"""

    completed_sections = state["completed_sections"]
    completed_section = format_sections(completed_sections)
    return {"report_sections_from_research": completed_section}


def write_final_sections(state: SectionState, config: RunnableConfig):
    """Write sections that dont require research using completed sections as context.
    This node handles sections such as conclusions or summaries that build on the researched sections
    rather than requiring new research.
    
    Args:
        state: current state with completed sections
        config: configuration for section writing
    
    Returns:
        Dict containing the completed report"""
    
    configurable = Configuration.from_runnable_config(config)
    topic = state["topic"]
    section = state["section"]
    completed_report_sections = state["report_sections_from_research"]

    system_instructions = final_section_writer_instructions.format(
        topic=topic,
        section_name=section.name,
        section_topic=section.description,
        context=completed_report_sections
    )

    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider)

    section_content = writer_model.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content="Generate a report section based on the provided sources")
    ])

    section.content = section_content.content

    return {"completed_sections": [section]}



def compile_final_report(state: ReportState):
    """Compile all sections into the final report.
    
    This node:
    1. Gets all completed sections
    2. Orders them according to original plan
    3. Combines them into the final report
    
    Args:
        state: Current state with all completed sections
        
    Returns:
        Dict containing the complete report
    """
    sections = state["sections"]
    completed_sections = {s.name: s.content for s in state["completed_sections"]}
    for section in sections:
        section.content = completed_sections[section.name]
    
    all_sections = "\n\n".join([s.content for s in sections])

    return {"final_report": all_sections}


def initiate_final_section_writing(state: ReportState):
    """Create a parallel tasks for writing non-research sections
    
    This node identifies sections that don't need research and creates
    parallel writing tasks for each one.
    
    Args:
        state: Current state with all sections and research context
        
    Returns:
        List of Send commands for parallel section writing tasks"""
    
    return [
        Send("write_final_sections", {"topic": state["topic"], "section": sec, "report_sections_from_research": state["report_sections_from_research"]})
        for sec in state["sections"]
        if not sec.research
    ]
