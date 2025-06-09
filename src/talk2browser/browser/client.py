"""Playwright client for browser automation."""
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


class PlaywrightClient:
    """Client for interacting with Playwright browser automation."""

    def __init__(self, headless: bool = False):
        """Initialize the Playwright client.
        
        Args:
            headless: Whether to run in headless mode
        """
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def start(self) -> None:
        """Start the Playwright browser instance."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_page_state(self) -> Dict[str, Any]:
        """Get the current state of the page.
        
        Returns:
            Dictionary containing page state information including:
            - url: Current page URL
            - title: Page title
            - interactive_elements: List of interactive elements on the page
            - screenshot: JPEG screenshot of the page
        """
        if not self.page:
            return {}
            
        # Import here to avoid circular imports
        from ..browser.dom.service import DOMService
        
        state = {
            "url": self.page.url,
            "title": await self.page.title(),
            "screenshot": await self.page.screenshot(type="jpeg", quality=70),
        }
        
        # Get interactive elements with highlighting
        try:
            dom_service = DOMService(self.page)
            elements = await dom_service.get_interactive_elements(highlight=True)
            state["interactive_elements"] = [
                {
                    "tag": el.tag_name,
                    "text": el.text,
                    "hash": el.element_hash,
                    "attributes": el.attributes,
                }
                for el in elements
            ]
        except Exception as e:
            logging.warning(f"Could not get interactive elements: {e}")
            state["interactive_elements"] = []
        
        return state

    # Context management is handled by the BrowserAgent
    # to prevent multiple browser instances from being created
