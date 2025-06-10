"""Browser automation tools using Playwright."""
from typing import Optional
from playwright.async_api import Page
from langchain.tools import tool

# Global page reference
_page: Optional[Page] = None

def set_page(page: Page) -> None:
    """Set the Playwright page to use for browser interactions."""
    global _page
    _page = page

@tool
async def navigate(url: str) -> str:
    """Navigate to a URL.
    
    Args:
        url: The URL to navigate to
        
    Returns:
        str: Confirmation message with the loaded URL and page title
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first.")
        
    await _page.goto(url)
    title = await _page.title()
    return f"Navigated to {url}. Page title: {title}"

@tool
async def click(selector: str) -> str:
    """Click on an element matching the CSS selector.
    
    Args:
        selector: CSS selector of the element to click
        
    Returns:
        str: Confirmation message with the clicked element
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    await _page.click(selector)
    return f"Clicked element: {selector}"
