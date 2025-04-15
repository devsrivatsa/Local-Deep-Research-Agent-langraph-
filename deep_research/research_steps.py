from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from state import SectionState, Queries
from search.search_utils import select_and_execute_search
from configuration import Configuration
from utils import get_config_value, get_search_params
from prompts import query_writer_instructions

def generate_queries(state: SectionState, config: RunnableConfig) -> Queries:
    """Generate search queries for researching a specific section.
    
    This node uses an LLM to generate targeted search queries based on the 
    section topic and description.
    
    Args:
        state: Current state containing section details
        config: Configuration including number of queries to generate
        
    Returns:
        Dict containing the generated search queries"""

    topic = state["topic"] 
    section = state["section"]

    configurable = Configuration.from_runnable_config(config)
    number_of_queries = configurable.number_of_queries
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model = get_config_value(configurable.writer_model)

    structured_llm = writer_model.with_structured_output(Queries)
    system_instructions = query_writer_instructions.format(topic=topic, section_topic=section.description, number_of_queries=number_of_queries)
    queries = structured_llm.invoke(
        SystemMessage(content=system_instructions),
        HumanMessage(content="Generate search queries on the provided topic.")
    )

    return queries


async def search_web(state: SectionState, config: RunnableConfig):
    """Execute web searches for the section queries.
    
    This node:
    1. Takes the generated queries
    2. Executes searches using configured search API
    3. Formats results into usable context
    
    Args:
        state: Current state with search queries
        config: Search API configuration
        
    Returns:
        Dict with search results and updated iteration count
    """

    search_queries = state["search_queries"]
    configurable = Configuration.from_runnable_config(config)
    search_api = get_config_value(configurable.search_api)
    search_api_config = configurable.search_api_config or {}
    search_params = get_search_params(search_api, search_api_config)
    query_list = [query.search_query for query in search_queries]
    source_str = await select_and_execute_search(search_api, query_list, search_params)
    
    return {"source_str": source_str, "search_iterations":state["search_iteration"]+ 1}

