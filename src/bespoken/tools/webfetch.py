"""Web fetch tool for retrieving and processing static web content."""

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
from rich import print
from langchain_core.tools import tool

from .. import config


def _debug_return(value: str) -> str:
    """Helper to show what the LLM receives from tools"""
    config.tool_debug(f"\n>>> Tool returning to LLM: {repr(value[:200])}...\n")
    return value


@tool
def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch content from a URL and convert to markdown.
    
    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        The fetched content as markdown
    """
    config.tool_debug(f">>> LLM calling tool: fetch_url(url={repr(url)})")
    config.tool_status(f"Fetching content from: {url}")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML and convert to markdown
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Convert to markdown
        markdown = markdownify(str(soup), heading_style="ATX")
        
        # Clean up excessive newlines
        markdown = '\n'.join(line for line in markdown.split('\n') if line.strip() or not line)
        
        config.tool_success(f"Successfully fetched {len(markdown):,} characters from {url}")
        return _debug_return(markdown)
        
    except requests.RequestException as e:
        error_msg = f"Failed to fetch {url}: {str(e)}"
        config.tool_error(error_msg)
        return _debug_return(f"Error: {error_msg}")


def WebFetchTool(timeout: int = 30) -> list:
    """Create a web fetch tool with the specified timeout."""
    def fetch_url_with_timeout(url: str) -> str:
        return fetch_url(url, timeout)
    
    return [fetch_url_with_timeout]


# Legacy class for backward compatibility
class WebFetchToolClass:
    """Tool for fetching and converting web content to markdown."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def _debug_return(self, value: str) -> str:
        """Helper to show what the LLM receives from tools"""
        config.tool_debug(f"\n>>> Tool returning to LLM: {repr(value[:200])}...\n")
        return value
    
    def fetch_url(self, url: str) -> str:
        return fetch_url(url, self.timeout)
    
