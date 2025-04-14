import os
import time
import logging
import aiohttp
import asyncio
import requests
import random
import concurrent.futures
from asyncio import Semaphore
from urllib.parse import unquote
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def get_useragent():
    """Generates a random user agent string."""
    lynx_version = f"Lynx/{random.randint(2, 3)}.{random.randint(8, 9)}.{random.randint(0, 2)}"
    libwww_version = f"libwww-FM/{random.randint(2, 3)}.{random.randint(13, 15)}"
    ssl_mm_version = f"SSL-MM/{random.randint(1, 2)}.{random.randint(3, 5)}"
    openssl_version = f"OpenSSL/{random.randint(1, 3)}.{random.randint(0, 4)}.{random.randint(0, 9)}"
    return f"{lynx_version} {libwww_version} {ssl_mm_version} {openssl_version}"

async def search_single_query_with_api(query: str, api_key: str, cx: str, max_results: int):
    results = []
    try:
        for start_idx in range(1, max_results+1, 10):
            num = min(10, max_results - (start_idx -1))
            params = {
                "q":query,
                "key": api_key,
                "cx": cx,
                "start": start_idx,
                "num": num
            }
            logger.info(f"Requesting {num} results for '{query}' with google search api")

            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Error fetching results for '{query}': {error_text}")
                        break
                    
                    data = await response.json()
                    for item in data.get("items", []):
                        result = {
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "content": item.get("snippet", ""),
                            "score": None,
                            "raw_content": item.get("snippet", "")
                        }
                        results.append(result)
                
                await asyncio.sleep(0.2) #respect api rate limits with a small delay

            # If we didn't get a full page of results, no need to request more
            if not data.get("items") or len(data.get("items", [])) < num:
                break
    except Exception as e:
        logger.error(f"Error fetching results using google search api for '{query}': {e}")

    return results


def search_single_query_with_scraping(query: str, max_results: int):
    try:
        lang = "en"
        safe = "active"
        start = 0
        fetched_results = 0
        fetched_links = set()
        search_results = []

        while fetched_results < max_results:
            resp = requests.get(
                url="https://www.google.com/search",
                headers={
                    "User-Agent": get_useragent(),
                    "Accept": "*/*",
                },
                params={
                    "q": query,
                    "num": max_results + 2,
                    "hl": lang,
                    "start": start,
                    "safe": safe,
                },
                cookies = {
                    "CONSENT": "PENDING+987",
                    "SOCS": "CAESHAgBEhIaAB"
                }
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            result_block = soup.find_all("div", _class="ezo2md")
            new_results = 0
            for result in result_block:
                link_tag = result.find("a", href=True)
                title_tag = result.find("span", class_="CVA68e") if link_tag else None
                description_tag = result.find("span",class_="FrIlee")
                if link_tag and title_tag and description_tag:
                   link = unquote(link_tag["href"].split("&")[0].replace("/url?q=", ""))
                   if link in fetched_links:
                       continue
                   fetched_links.add(link)
                   title = title_tag.text
                   description = description_tag.text
                   search_results.append({
                       "title": title,
                       "url": link,
                       "content": description,
                       "score": None,
                       "raw_content": description
                   })
                   new_results += 1
                   fetched_results += 1

                   if fetched_results >= max_results:
                       break
            if new_results == 0:
                break
            start += 10
            time.sleep(1) #delay between pages
        
        return search_results
    except Exception as e:
        logger.error(f"Error fetching results for '{query}': {e}")
        return []
    

async def fetch_full_content(result, content_semaphore, session):
    async with content_semaphore:
        url = result["url"]
        headers = {
            "User-Agent": get_useragent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.",
        }
        try:
            await asyncio.sleep(0.2 + random.random()*0.6)
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/pdf" in content_type or "application/octet-stream" in content_type:
                        result["raw_content"] = f"[Binary content: {content_type}. Content extraction not supported for this type of file]"
                    else:
                        try:
                            html = await response.text(errors="replace")
                            soup = BeautifulSoup(html, "html.parser")
                            result["raw_content"] = soup.get_text()
                        except UnicodeDecodeError as ude:
                            result["raw_content"] = f"[Could not decode content: {str(ude)}]"
        except Exception as e:
            logger.error(f"Warning: Failed to fetch content for {url}: {str(e)}")
            result["raw_content"] = f"[Error fetching content: {str(e)}]"
        
        return result

    
async def search_single_query(
        semaphore: Semaphore, 
        executor: concurrent.futures.ThreadPoolExecutor, 
        query: str, max_results: int, include_raw_content: bool,
        use_api: bool, api_key: str, cx: str
        ):
    try:
        async with semaphore:
            if use_api:
                search_results = await search_single_query_with_api(query, api_key, cx, max_results)
            else:
                loop = asyncio.get_running_loop()
                search_results = await loop.run_in_executor(
                    executor,
                    lambda: search_single_query_with_scraping(query, max_results)
                )
            
            results = search_results
            if include_raw_content and results:
                content_semaphore = asyncio.Semaphore(3)
                async with aiohttp.ClientSession() as session:
                    fetch_tasks = []
                    
                    for result in results:
                        fetch_tasks.append(fetch_full_content(result))
                    
                    updated_results = await asyncio.gather(*fetch_tasks)
                    results = updated_results
                    logger.info(f"Fetched full content for {len(results)} results")
            
            return {
                "query": query,
                "follow_up_questions": None,
                "answer": [],
                "results": results
            }
    except Exception as e:
        logger.error(f"Error fetching results for '{query}': {e}")
        return {
            "query": query,
            "follow_up_questions": None,
            "answer": None,
            "images": [],
            "results": []
        }


async def google_search(
        search_queries: str | list[str],
        max_results: int = 5,
        include_raw_content: bool = True,
):
    """
    Performs concurrent web searches using Google.
    Uses Google Custom Search API if environment variables are set, otherwise falls back to web scraping.

    Args:
        search_queries (List[str]): List of search queries to process
        max_results (int): Maximum number of results to return per query
        include_raw_content (bool): Whether to fetch full page content

    Returns:
        List[dict]: List of search responses from Google, one per query
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    use_api = bool(api_key and cx)

    if isinstance(search_queries, str):
        search_queries = [search_queries]
    
    semaphore = asyncio.Semaphore(5 if use_api else 2)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5) if not use_api else None

    try:
        search_tasks = [
            search_single_query(semaphore, executor, query, max_results, include_raw_content, use_api, api_key, cx) 
            for query in search_queries]
        
        search_results = await asyncio.gather(*search_tasks)
        return search_results
    except Exception as e:
        logger.error(f"Error fetching results: {e}")
        return []
    finally:
        if executor:
            executor.shutdown(wait=False)
    
