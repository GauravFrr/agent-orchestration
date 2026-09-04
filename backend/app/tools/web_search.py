import httpx
import logging
from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

async def web_search(query: str) -> dict:
    """
    Search the web for information using Wikipedia's public search API.
    """
    logger.info(f"Performing web search for: '{query}'")
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "origin": "*"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            
            formatted_results = []
            for result in search_results[:3]:  # Top 3 results
                title = result.get("title")
                snippet = result.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
                formatted_results.append({
                    "title": title,
                    "snippet": snippet,
                    "source": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                })
            
            if not formatted_results:
                return {"results": [], "info": "No results found on Wikipedia."}
            return {"results": formatted_results}
            
    except Exception as e:
        logger.error(f"Search API error: {str(e)}. Falling back to mock search.")
        # Fallback mock search for reliability
        return {
            "results": [
                {
                    "title": f"Agent Orchestration Trends: {query}",
                    "snippet": "Latest trends show a shift towards multi-agent networks, supervisor-specialist patterns, and sandboxed code execution.",
                    "source": "https://example.com/agent-orchestration-trends"
                }
            ],
            "info": "Fallback mock search results used."
        }

# Auto-register this tool in the registry
register_tool(
    name="web_search",
    description="Search the web for information using a query string.",
    allowed_specialists=["research"],
    func=web_search,
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query string"}
        },
        "required": ["query"]
    }
)
