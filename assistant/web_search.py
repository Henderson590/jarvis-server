"""Web search: Google (Custom Search API) or DuckDuckGo fallback."""
from __future__ import annotations

import os
from typing import List

import config


def _google_search(query: str, max_results: int) -> List[dict]:
    """Use Google Custom Search JSON API. Returns list of dicts with title, url, snippet."""
    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "").strip() or (config.GOOGLE_SEARCH_API_KEY or "").strip()
    cx = os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "").strip() or (config.GOOGLE_SEARCH_ENGINE_ID or "").strip()
    if not api_key or not cx:
        return []
    try:
        import requests
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(max_results, 10),
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        out = []
        for item in data.get("items", [])[:max_results]:
            out.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return out
    except Exception:
        return []


def _duckduckgo_search(query: str, max_results: int) -> List[dict]:
    """Fallback: DuckDuckGo (no API key)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        out = []
        for r in results:
            out.append({
                "title": r.get("title", ""),
                "url": r.get("href", r.get("url", "")),
                "snippet": r.get("body", r.get("snippet", "")),
            })
        return out
    except Exception as e:
        return [{"title": "Error", "url": "", "snippet": str(e)}]


def search(query: str, max_results: int | None = None) -> List[dict]:
    """
    Search the web. Uses Google if API key and engine ID are set, else DuckDuckGo.
    Returns list of dicts with keys: title, url, snippet.
    """
    max_results = max_results or config.WEB_SEARCH_MAX_RESULTS
    results = _google_search(query, max_results)
    if not results:
        results = _duckduckgo_search(query, max_results)
    return results


def search_summary(query: str, max_results: int = 3) -> str:
    """Return a single string summary of search results for the query."""
    results = search(query, max_results=max_results)
    if not results or (len(results) == 1 and "Error" in results[0].get("title", "")):
        return f"Search failed or no results for: {query}"
    lines = [f"Search results for \"{query}\":"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '')} - {r.get('url', '')}")
        lines.append(f"   {r.get('snippet', '')}")
    return "\n".join(lines)
