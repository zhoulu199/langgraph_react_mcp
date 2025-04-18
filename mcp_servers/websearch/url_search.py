import os
import re
import asyncio
import time
import random
import json
from typing import List, Dict, Any, Optional, Union, Set
from functools import lru_cache
from dataclasses import dataclass
import logging
from urllib.parse import quote_plus
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from googlesearch import search as google_search

import ssl
import certifi
from aiohttp import TCPConnector
from bs4 import BeautifulSoup
import socket
from aiohttp.resolver import AsyncResolver


from mcp.server.fastmcp import FastMCP

# 创建 MCP 服务器
mcp = FastMCP("ws-find-url-Server")




# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to get USER_AGENT from environment, otherwise use a generic one
USER_AGENT = os.environ.get('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

# Cache settings
CACHE_ENABLED = True
CACHE_DIR = os.path.expanduser("~/.shandu/cache/search")
CACHE_TTL = 86400  # 24 hours in seconds

if CACHE_ENABLED and not os.path.exists(CACHE_DIR):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create cache directory: {e}")
        CACHE_ENABLED = False

@dataclass
class SearchResult:
    """Class to store search results."""
    url: str
    title: str
    snippet: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source
        }

class UnifiedSearcher:
    def __init__(self,
                 max_results: int = 10,
                 cache_enabled: bool = CACHE_ENABLED,
                 cache_ttl: int = CACHE_TTL):
        self.max_results = max_results
        self.user_agent = USER_AGENT
        self.default_engine = "google"
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.in_progress_queries: Set[str] = set()
        self._semaphores = {}
        self._semaphore_lock = asyncio.Lock()

    async def search(self, query: str, engines: Optional[List[str]] = None, force_refresh: bool = False) -> List[SearchResult]:
        """
        Search for a query using multiple engines.

        Args:
            query: Query to search for
            engines: List of engines to use (google, duckduckgo, bing, etc.)
            force_refresh: Whether to ignore cache and force fresh searches

        Returns:
            List of search results
        """
        if engines is None:
            engines = ["google"]

        if isinstance(engines, str):
            engines = [engines]

        # Use set to ensure unique engine names (case insensitive)
        unique_engines = set(engine.lower() for engine in engines)

        tasks = []
        for engine in unique_engines:
            # Skip unsupported engines
            if engine not in ["google", "duckduckgo", "bing", "wikipedia"]:
                logger.warning(f"Unknown search engine: {engine}")
                continue

            # First check cache unless forcing refresh
            if not force_refresh:
                cached_results = await self._check_cache(query, engine)
                if cached_results:
                    logger.info(f"Using cached results for {query} on {engine}")
                    tasks.append(asyncio.create_task(asyncio.sleep(0, result=cached_results)))
                    continue

            # Execute search with appropriate engine method
            if engine == "google":
                tasks.append(self._search_with_retry(self._search_google, query))
            elif engine == "duckduckgo":
                tasks.append(self._search_with_retry(self._search_duckduckgo, query))
            elif engine == "bing":
                tasks.append(self._search_with_retry(self._search_bing, query))
            elif engine == "wikipedia":
                tasks.append(self._search_with_retry(self._search_wikipedia, query))


        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and filter out exceptions
        all_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error during search: {result}")
            else:
                all_results.extend(result)

        unique_urls = set()
        unique_results = []

        for result in all_results:
            if result.url not in unique_urls:
                unique_urls.add(result.url)
                unique_results.append(result)

        # Shuffle results to mix engines
        random.shuffle(unique_results)

        # Limit to max_results
        return unique_results[:self.max_results]

    async def _search_with_retry(self, search_function, query: str, max_retries: int = 2) -> List[SearchResult]:
        """Wrapper that adds retry logic to search functions."""
        retries = 0
        engine_name = search_function.__name__.replace("_search_", "")

        while retries <= max_retries:
            try:

                if retries > 0:
                    delay = random.uniform(1.0, 3.0) * retries
                    await asyncio.sleep(delay)

                semaphore = await self._get_semaphore()

                # Acquire semaphore to limit concurrent searches
                async with semaphore:

                    await asyncio.sleep(random.uniform(0.1, 0.5))

                    # Execute the search
                    results = await search_function(query)

                    # Cache successful results
                    if results:
                        await self._save_to_cache(query, engine_name, results)

                    return results

            except Exception as e:
                logger.warning(f"Search attempt {retries + 1} failed for {engine_name}: {e}")
                retries += 1
                if retries > max_retries:
                    logger.error(f"All {max_retries + 1} attempts failed for {engine_name} search: {e}")
                    return []

    async def _search_google(self,query: str) -> List[SearchResult]:
        """
        Search Google for a query asynchronously.

        Args:
            query: Query to search for
            max_retries: Number of retries for search in case of failure
            timeout: Timeout for search request
            max_results: Maximum number of results to return

        Returns:
            List of search results as SearchResult objects
        """
        results = []

        for attempt in range(1, 5):
            try:
                # 执行实际搜索并处理结果
                raw = google_search(
                    query,
                    num_results=self.max_results, 
                    advanced=True,
                    timeout=10
                )
                # 结构化处理结果
                for idx, item in enumerate(raw):
                    title = getattr(item, 'title', f"默认标题 {idx + 1}")
                    url = getattr(item, 'url', '')
                    description = generate_summary(self,str(getattr(item, 'description'," ")))
                    search_result = SearchResult(
                        title=title,
                        url=url,
                        snippet=description,
                        source="google"
                    )
                    results.append(search_result)
                    if len(results) >= self.max_results:
                        break
                return results


            except asyncio.TimeoutError:
                logger.warning(f"Timeout during Google search for query: {query}")
                raise
            except Exception as e:
                logger.error(f"Error during Google search: {e}")
                raise  # Re-raise for retry mechanism

    async def _search_duckduckgo(self, query: str) -> List[SearchResult]:
        """
        Search DuckDuckGo for a query.

        Args:
            query: Query to search for

        Returns:
            List of search results
        """
        try:

            timeout = aiohttp.ClientTimeout(total=15)  # 15 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:

                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                headers = {"User-Agent": self.user_agent}

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"DuckDuckGo search returned status code {response.status}")
                        raise ValueError(f"DuckDuckGo search returned status code {response.status}")

                    html = await response.text()
                    soup = BeautifulSoup(html, features="html.parser")

                    results = []
                    for result in soup.find_all("div", class_="result"):

                        title_elem = result.find("a", class_="result__a")
                        if not title_elem:
                            continue

                        title = title_elem.text.strip()

                        url = title_elem.get("href", "")
                        if not url:
                            continue

                        if url.startswith("/"):
                            url = "https://duckduckgo.com" + url

                        snippet_elem = result.find("a", class_="result__snippet")
                        snippet = snippet_elem.text.strip() if snippet_elem else ""

                        search_result = SearchResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            source="DuckDuckGo"
                        )
                        results.append(search_result)

                        # Limit to max_results
                        if len(results) >= self.max_results:
                            break

                    return results

        except asyncio.TimeoutError:
            logger.warning(f"Timeout during DuckDuckGo search for query: {query}")
            raise
        except Exception as e:
            logger.error(f"Error during DuckDuckGo search: {e}")
            raise  # Re-raise for retry mechanism

    async def _search_bing(self, query: str) -> List[SearchResult]:
        """
        Search Bing for a query.

        Args:
            query: Query to search for

        Returns:
            List of search results
        """
        try:

            timeout = aiohttp.ClientTimeout(total=15)  # 15 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:

                url = f"https://www.bing.com/search?q={quote_plus(query)}"
                headers = {"User-Agent": self.user_agent}

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Bing search returned status code {response.status}")
                        raise ValueError(f"Bing search returned status code {response.status}")

                    html = await response.text()
                    soup = BeautifulSoup(html, features="html.parser")

                    results = []
                    for result in soup.find_all("li", class_="b_algo"):

                        title_elem = result.find("h2")
                        if not title_elem:
                            continue

                        title = title_elem.text.strip()

                        url_elem = title_elem.find("a")
                        if not url_elem:
                            continue

                        url = url_elem.get("href", "")
                        if not url:
                            continue

                        snippet_elem = result.find("div", class_="b_caption")
                        snippet = ""
                        if snippet_elem:
                            p_elem = snippet_elem.find("p")
                            if p_elem:
                                snippet = p_elem.text.strip()

                        search_result = SearchResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            source="Bing"
                        )
                        results.append(search_result)

                        # Limit to max_results
                        if len(results) >= self.max_results:
                            break

                    return results

        except asyncio.TimeoutError:
            logger.warning(f"Timeout during Bing search for query: {query}")
            raise
        except Exception as e:
            logger.error(f"Error during Bing search: {e}")
            raise  # Re-raise for retry mechanism

    async def _search_wikipedia(self, query: str) -> List[SearchResult]:
        """
        Search Wikipedia for a query.

        Args:
            query: Query to search for

        Returns:
            List of search results
        """
        try:

            timeout = aiohttp.ClientTimeout(total=15)  # 15 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:

                url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={quote_plus(query)}&limit={self.max_results}&namespace=0&format=json"
                headers = {"User-Agent": self.user_agent}

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Wikipedia search returned status code {response.status}")
                        raise ValueError(f"Wikipedia search returned status code {response.status}")

                    data = await response.json()

                    results = []
                    for i in range(len(data[1])):
                        title = data[1][i]
                        snippet = data[2][i]
                        url = data[3][i]

                        result = SearchResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            source="Wikipedia"
                        )
                        results.append(result)

                    return results

        except asyncio.TimeoutError:
            logger.warning(f"Timeout during Wikipedia search for query: {query}")
            raise
        except Exception as e:
            logger.error(f"Error during Wikipedia search: {e}")
            raise  # Re-raise for retry mechanism


    def search_sync(self, query: str, engines: Optional[List[str]] = None, force_refresh: bool = False) -> List[
        SearchResult]:
        """
        Synchronous version of search.

        Args:
            query: Query to search for
            engines: List of engines to use
            force_refresh: Whether to ignore cache and force fresh searches

        Returns:
            List of search results
        """
        return asyncio.run(self.search(query, engines, force_refresh))

    async def _get_semaphore(self) -> asyncio.Semaphore:
        """
        Get or create a semaphore for the current event loop.

        This ensures that each thread has its own semaphore bound to the correct event loop.
        """
        try:

            loop = asyncio.get_event_loop()
            loop_id = id(loop)

            # If we already have a semaphore for this loop, return it
            if loop_id in self._semaphores:
                return self._semaphores[loop_id]

            # Otherwise, create a new one
            async with self._semaphore_lock:
                # Double-check if another task has created it while we were waiting
                if loop_id in self._semaphores:
                    return self._semaphores[loop_id]

                semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
                self._semaphores[loop_id] = semaphore
                return semaphore

        except RuntimeError:
            # If we can't get the event loop, create a new one and a semaphore for it
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            semaphore = asyncio.Semaphore(5)

            loop_id = id(loop)
            self._semaphores[loop_id] = semaphore
            return semaphore

    async def _check_cache(self, query: str, engine: str) -> Optional[List[SearchResult]]:
        """Check if results for the given query and engine exist in the cache."""
        if not self.cache_enabled:
            return None

        formatted_query = self._get_formatted_query(query, engine)
        cache_file_path = os.path.join(CACHE_DIR, f"{formatted_query}.json")

        if os.path.exists(cache_file_path):
            try:
                modified_time = os.path.getmtime(cache_file_path)
                if (time.time() - modified_time) < self.cache_ttl:
                    with open(cache_file_path, 'r') as f:
                        data = json.load(f)
                        return [SearchResult(**item) for item in data]
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_file_path}: {e}")
                return None
        return None

    async def _save_to_cache(self, query: str, engine: str, results: List[SearchResult]):
        """Save search results to the cache."""
        if self.cache_enabled:
            formatted_query = self._get_formatted_query(query, engine)
            cache_file_path = os.path.join(CACHE_DIR, f"{formatted_query}.json")
            try:
                with open(cache_file_path, 'w') as f:
                    json.dump([result.to_dict() for result in results], f)
            except Exception as e:
                logger.warning(f"Error writing to cache file {cache_file_path}: {e}")

    def _get_formatted_query(self, query: str, engine: str) -> str:
        """
        Formats the query and engine name into a safe filename component.
        Replaces non-alphanumeric characters with underscores.
        """
        # Combine query and engine for uniqueness
        combined = f"{engine}_{query}"
        # Keep it reasonably short
        max_len = 100
        if len(combined) > max_len:
            combined = combined[:max_len]
        # Replace potentially problematic characters for filenames
        safe_filename = re.sub(r'[^\w\-.]', '_', combined)
        return safe_filename




def generate_summary(self, text: str, max_len=150) -> str:
    """自动生成摘要并清理多余的换行符和空行"""
    if not text:
        return ""

    # 去掉所有换行符、空行和多余的空白字符
    cleaned_text = re.sub(r'\s+', ' ', text).strip()

    # 截取指定长度的摘要
    if len(cleaned_text) > max_len:
        # 截取前 max_len 个字符
        summary = cleaned_text[:max_len].strip()
        # 如果截断的位置不是句号或空格，添加省略号
        if not (summary.endswith('.') or summary.endswith(' ')):
            summary += '...'
        return summary
    else:
        return cleaned_text


# @mcp.tool()
# async def search(query: str, engines: Optional[List[str]] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
#     searcher = UnifiedSearcher(max_results=10)
#     results = await searcher.search(query,engines,force_refresh)
#     return [result.to_dict() for result in results]


# if __name__ == "__main__":
#     # 创建搜索器实例
#     """
#     searcher = UnifiedSearcher(max_results=10)
#     all_results = []  # 用于存储所有查询的结果

#     # 定义你要搜索的查询
#     my_query = ['下雨降雨量最大的地方']

#     # --- 方式一：使用异步方法 (推荐) ---
#     for item in my_query:
#         print(f"--- Running async search for: '{item}' ---")
#         # 使用 asyncio.run 来执行异步的 search 方法
#         results_async = asyncio.run(searcher.search(item, engines=["google"]))
#         all_results.extend(results_async)  # 将结果累积到全局列表中

#     # 打印所有结果
#     print(f"\nFound {len(all_results)} total results:")
#     for i, result in enumerate(all_results):
#         print(f"{i + 1}. [{result.source}] {result.title}")
#         print(f"   URL: {result.url}")
#         print(f"   Snippet: {result.snippet[:100]}...")
#         print("-" * 10)
#     """
#     mcp.run(transport='stdio')