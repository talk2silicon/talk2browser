import logging
from playwright.async_api import Page
from .dom.service import DOMService

logger = logging.getLogger(__name__)

class BrowserPage:
    """
    Encapsulates a Playwright page and its associated DOMService.
    Each browser tab/window/popup should have its own BrowserPage instance.
    """
    def __init__(self, page: Page):
        self.page = page
        self.dom_service = DOMService(page)
        logger.debug(f"BrowserPage created for page: {getattr(page, 'url', None)}")

    async def refresh_dom(self, highlight: bool = False):
        """Refresh the DOMService's list of interactive elements."""
        logger.info("Refreshing DOM for BrowserPage...")
        return await self.dom_service.get_interactive_elements(highlight=highlight)

    def get_dom_service(self) -> DOMService:
        return self.dom_service

    def get_page(self) -> Page:
        return self.page
