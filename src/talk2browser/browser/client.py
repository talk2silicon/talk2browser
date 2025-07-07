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
        """Start the Playwright browser instance with large window and viewport."""
        self.playwright = await async_playwright().start()
        window_width, window_height = 1920, 1080
        launch_args = [f"--window-size={window_width},{window_height}"]
        logging.info(f"Launching Chromium with window size: {window_width}x{window_height}")
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=launch_args
        )
        logging.info(f"Creating browser context with viewport: {window_width}x{window_height}")
        self.context = await self.browser.new_context(
            viewport={'width': window_width, 'height': window_height}
        )
        self.page = await self.context.new_page()
        logging.info(f"Browser page created. Viewport and window size should now be set.")

        # --- New Tab/Popup Handling ---
        import uuid
        from .page_manager import PageManager
        from .page import BrowserPage

        def _on_new_page(page):
            page_id = str(uuid.uuid4())
            browser_page = BrowserPage(page)
            PageManager.get_instance().add_page(page_id, browser_page)
            PageManager.get_instance().switch_to(page_id)
            logging.info(f"[PlaywrightClient] New tab registered and switched: {page_id}, url={getattr(page, 'url', None)}")

        self.context.on("page", _on_new_page)
        # --- End New Tab/Popup Handling ---

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
        import asyncio
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                title = await self.page.title()
                break
            except Exception as e:
                if "Execution context was destroyed" in str(e) and attempt < max_retries - 1:
                    logging.warning(f"[PlaywrightClient] page.title() failed due to navigation context destruction, retrying ({attempt+1}/{max_retries})...")
                    await asyncio.sleep(0.5)
                    try:
                        await self.page.wait_for_load_state('load')
                    except Exception:
                        pass
                    continue
                else:
                    logging.error(f"[PlaywrightClient] Failed to get page title after navigation: {e}")
                    title = ""
                    break
        state = {
            "url": self.page.url,
            "title": title,
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
