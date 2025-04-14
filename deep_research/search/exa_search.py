from typing import Optional, List
from exa_py import Exa
import asyncio
import os


exa = Exa(api_key=f"{os.getenv('EXA_API_KEY')}")

def get_value(item:dict, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    else:
        return getattr(item, key, default) if hasattr(item, key) else default
    

def exa_search_fn(
        query:str,
        num_results:int, 
        max_characters:Optional[int]=None,
        subpages:Optional[int]=None,
        include_domains:Optional[List[str]]=None,
        exclude_domains:Optional[List[str]]=None
        ):
    kwargs = {
        "text": True if max_characters is None else False,
        "summary": True,
        "num_results":num_results
    }
    if subpages is not None:
        kwargs["subpages"] = subpages
    if include_domains is not None:
        kwargs["include_domains"] = include_domains
    if exclude_domains is not None:
        kwargs["exclude_domains"] = exclude_domains
    
    return exa.search_and_contents(query, **kwargs)

async def process_query(query: str, subpages:Optional[int]=None):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, exa_search_fn)
    formatted_results = []
    seen_urls = set()
    result_list = get_value(response, "results", [])
    for result in result_list:
        score = get_value(result, "score")
        text_content = get_value(result, "text", "")
        summary_content = get_value(result, "summary", "")
        content = text_content
        if summary_content:
            if content:
                content = f"{summary_content}\n\n{content}"
            else:
                content = summary_content
        title = get_value(result, "title", "")
        url = get_value(result, "url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        result_entry = {
            "title":title, 
            "url": url,
            "content": content,
            "score": score,
            "raw_content": text_content
        }
        formatted_results.append(result_entry)
    
    if subpages is not None:
        for result in result_list:
            subpages = get_value(result, "subpages", [])
            for subpage in subpages:    
                subpage_score = get_value(subpage, "score", 0)
                subpage_title = get_value(subpage, "title", "")
                subpage_summary = get_value(subpage, "summary", "")
                subpage_url = get_value(subpage, "url", "")
                subpage_text = get_value(subpage, "text", "")
                subpage_content = subpage_text
                if subpage_summary:
                    if subpage_content:
                        subpage_content = f"{subpage_summary}\n\n{subpage_content}"
                    else:
                        subpage_content = subpage_summary
                if subpage_url not in seen_urls:
                    seen_urls.add(subpage_url)
                    formatted_results.append(
                        {
                            "title": subpage_title, 
                            "url": subpage_url, 
                            "content": subpage_content, 
                            "score": subpage_score,
                            "raw_content": subpage_text
                        }
                    )
                else:
                    continue
    
    images = []
    for result in result_list:
        image = get_value(result, "image")
        if image and image not in images:
            images.append(image)
    
    return {
        "query": query,
        "results": formatted_results,
        "images": images,
        "follow_up_questions": None,
        "answer": None
    }

    

async def exa_search(
    search_queries, 
    include_domains:Optional[List[str]]=None,
    exclude_domains:Optional[List[str]]=None,
    subpages:Optional[int]=None):
    """Search the web using the Exa API.
    
    Args:
        search_queries (List[SearchQuery]): List of search queries to process
        max_characters (int, optional): Maximum number of characters to retrieve for each result's raw content.
                                       If None, the text parameter will be set to True instead of an object.
        num_results (int): Number of search results per query. Defaults to 5.
        include_domains (List[str], optional): List of domains to include in search results. 
            When specified, only results from these domains will be returned.
        exclude_domains (List[str], optional): List of domains to exclude from search results.
            Cannot be used together with include_domains.
        subpages (int, optional): Number of subpages to retrieve per result. If None, subpages are not retrieved.
        
    Returns:
        List[dict]: List of search responses from Exa API, one per query. Each response has format:
            {
                'query': str,                    # The original search query
                'follow_up_questions': None,      
                'answer': None,
                'images': list,
                'results': [                     # List of search results
                    {
                        'title': str,            # Title of the search result
                        'url': str,              # URL of the result
                        'content': str,          # Summary/snippet of content
                        'score': float,          # Relevance score
                        'raw_content': str|None  # Full content or None for secondary citations
                    },
                    ...
                ]
            }
    """
    if include_domains and exclude_domains: 
        raise ValueError("Cannot use both include_domains and exclude_domains")
    
    search_docs = []
    for i, query in enumerate(search_queries):
        try:
            if i > 0:
                await asyncio.sleep(0.25)
            result = await process_query(query, subpages)
            search_docs.append(result)
        except Exception as e:
            print(f"Error processing query '{query}': {str(e)}")
            search_docs.append({
                "query": query,
                "follow_up_questions": None,
                "answer": None,
                "images": [],
                "results": [],
                "error": str(e)
            })

            if "429" in str(e):
                print("Rate limit exceeded. Adding additional delay...")
                await asyncio.sleep(1.0)
    
    return search_docs
    