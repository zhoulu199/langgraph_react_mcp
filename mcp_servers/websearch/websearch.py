from typing import List, Dict, Any, Optional
import asyncio
from url_search import UnifiedSearcher, SearchResult
from scraper import WebScraper, ScrapedContent
import logging

logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

# 创建 MCP 服务器
mcp = FastMCP("websearch-MCP-Server")


@mcp.tool()
async def search_and_scrape(query: str,force_refresh: bool = True) -> List[Dict[str, Any]]:
    """
    搜索功能并爬取前几个搜索结果的网页内容。

    Args:
        query: 搜索功能。
        engines: 使用的搜索引擎列表。
        force_refresh: 是否忽略缓存，强制刷新搜索结果。

    Returns:
        List[Dict[str, Any]]: 爬取结果的字典列表。
    """
    engines = ['google']
    try:
        searcher = UnifiedSearcher(max_results=10)
        search_results = await searcher.search(query, engines, force_refresh)
        urls_to_scrape = [result.url for result in search_results[:5]]
        if not urls_to_scrape:
            return []
        scraper = WebScraper()
        scrape_results = await scraper.scrape_urls(urls_to_scrape, dynamic=False, force_refresh=force_refresh)
        return [result.to_dict() for result in scrape_results]
    except Exception as e:
        logger.error(f"Error during search and scrape: {e}")
        return []


if __name__ == "__main__":
    print("Subqueries MCP Server running")
    mcp.run(transport='stdio')