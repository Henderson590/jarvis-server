"""Web search and browser tools. Browser control opens the user's default
browser/search engine rather than hardcoding one (Playwright-based DOM control
lands in Phase 4 - for now this drives the OS-level browser)."""
from __future__ import annotations

from .. import computer, web_search
from .registry import tool


@tool(
    "web_search",
    "Search the web and get a summary of the top results. Use this to answer questions "
    "about current events, facts, or anything you're not sure about.",
    parameters={"query": {"type": "string", "description": "Search query"}},
    required=["query"],
)
def search(query: str) -> str:
    return web_search.search_summary(query)


@tool(
    "open_browser_search",
    "Open the default web browser and perform a search for a query.",
    parameters={"query": {"type": "string", "description": "What to search for"}},
    required=["query"],
)
def open_browser_search(query: str) -> str:
    return computer.open_browser_search(query)


@tool(
    "open_website",
    "Open a specific URL or website in the default browser.",
    parameters={"url": {"type": "string", "description": "URL or site name, e.g. 'https://github.com' or 'github'"}},
    required=["url"],
)
def open_website(url: str) -> str:
    return computer.open_browser_url(url)


@tool(
    "search_within_site",
    "Open a specific website and search within it, e.g. search 'wireless mouse' on 'amazon'.",
    parameters={
        "site": {"type": "string", "description": "Site name, e.g. 'amazon', 'youtube', 'wikipedia'"},
        "query": {"type": "string", "description": "What to search for on that site"},
    },
    required=["site", "query"],
)
def search_within_site(site: str, query: str) -> str:
    return computer.open_site_search(site, query)


@tool(
    "play_youtube_video",
    "Search YouTube for a query and start playing the first result.",
    parameters={"query": {"type": "string", "description": "What to search for on YouTube"}},
    required=["query"],
)
def play_youtube_video(query: str) -> str:
    return computer.open_first_youtube_video(query)


@tool(
    "search_and_add_to_cart",
    "Search for a product on a shopping site and add the first result to the cart. "
    "This is a purchase-adjacent action - always confirm with the user first.",
    parameters={
        "site": {"type": "string", "description": "Shopping site, e.g. 'amazon'"},
        "query": {"type": "string", "description": "Product to search for"},
    },
    required=["site", "query"],
    confirm=True,
)
def search_and_add_to_cart(site: str, query: str) -> str:
    return computer.search_site_and_add_first_to_cart(site, query)
