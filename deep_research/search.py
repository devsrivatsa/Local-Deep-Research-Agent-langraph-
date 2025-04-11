







def deduplicate_and_format_sources(search_response, max_tokens_per_source, include_raw_content=True):
    """
    Takes a list of search responses and formats them into a readable string.
    Limits the raw_content to approximately max_tokens_per_source tokens.
 
    Args:
        search_responses: List of search response dicts, each containing:
            - query: str
            - results: List of dicts with fields:
                - title: str
                - url: str
                - content: str
                - score: float
                - raw_content: str|None
        max_tokens_per_source: int
        include_raw_content: bool
            
    Returns:
        str: Formatted string with deduplicated sources
    """
    sources_list = []
    for response in search_response:
        sources_list.extend(response['results'])
    
    unique_sources = {source['url']: source for source in sources_list}
    formatted_text = "Content from sources:\n"
    for i, source in enumerate(unique_sources.values()):
        formatted_text += f"{'='*80}\n"  # Clear section separator
        formatted_text += f"Source: {source['title']}\n"
        formatted_text += f"{'-'*80}\n"  # Subsection separator
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += f"Most relevant content from source: {source['content']}\n===\n"
        if include_raw_content:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            # Handle None raw_content
            raw_content = source.get('raw_content', '')
            if raw_content is None:
                raw_content = ''
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
        formatted_text += f"{'='*80}\n\n" # End section separator
                
    return formatted_text.strip()






async def select_and_execute_search(search_api, query_list, search_params) -> str:
    """Select and execute the appropriate search API.
    
    Args:
        search_api: Name of the search API to use
        query_list: List of search queries to execute
        params_to_pass: Parameters to pass to the search API
        
    Returns:
        Formatted string containing search results
        
    Raises:
        ValueError: If an unsupported search API is specified
    """
    if search_api == "tavily":
        search_result = await tavily_search(query_list, **search_params)
    elif search_api == "exa":
        search_result = await exa_search(query_list, **search_params)
    elif search_api == "axriv":
        search_result = await axriv_search(query_list, **search_params)
    elif search_api == "pubmed":
        search_result = await pubmed_search(query_list, **search_params)
    elif search_api == "duckduckgo":
        search_result = await duckduckgo_search(query_list, **search_params)
    elif search_api == "google":
        search_result = await google_search(query_list, **search_params)
    else:
        raise ValueError(f"Unsupported search API: {search_api}")
    
    return deduplicate_and_format_sources(search_result)



