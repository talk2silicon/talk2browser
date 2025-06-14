import logging
from typing import Dict, Optional, List
from .page import BrowserPage

class PageManager:
    """
    Manages multiple BrowserPage instances (tabs/windows/popups) and tracks the current active page.
    Provides methods to create, switch, close, and list pages.
    Implements the singleton pattern so all code can use PageManager.get_instance().
    """
    _instance = None

    def __init__(self):
        self.pages: Dict[str, BrowserPage] = {}  # key: page_id or url
        self.current_page_id: Optional[str] = None
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"PageManager instance id: {id(self)}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            logging.getLogger(__name__).debug(f"Created PageManager singleton id: {id(cls._instance)}")
        else:
            logging.getLogger(__name__).debug(f"Using existing PageManager singleton id: {id(cls._instance)}")
        return cls._instance

    def add_page(self, page_id: str, browser_page: BrowserPage):
        self.pages[page_id] = browser_page
        self.logger.info(f"Added BrowserPage with id {page_id}")
        if self.current_page_id is None:
            self.current_page_id = page_id
        self.logger.debug(f"Current page id after add: {self.current_page_id}")
        self.logger.debug(f"PageManager instance id in add_page: {id(self)}")

    def switch_to(self, page_id: str) -> Optional[BrowserPage]:
        if page_id in self.pages:
            self.current_page_id = page_id
            self.logger.info(f"Switched to BrowserPage with id {page_id}")
            self.logger.debug(f"PageManager instance id in switch_to: {id(self)}")
            return self.pages[page_id]
        self.logger.error(f"Page id {page_id} not found in PageManager")
        return None

    def close_page(self, page_id: str):
        if page_id in self.pages:
            del self.pages[page_id]
            self.logger.info(f"Closed BrowserPage with id {page_id}")
            if self.current_page_id == page_id:
                self.current_page_id = next(iter(self.pages), None)
        else:
            self.logger.error(f"Attempted to close non-existent page id {page_id}")
        self.logger.debug(f"PageManager instance id in close_page: {id(self)}")

    def get_current_page(self) -> Optional[BrowserPage]:
        self.logger.debug(f"PageManager instance id in get_current_page: {id(self)} | current_page_id: {self.current_page_id}")
        if self.current_page_id:
            return self.pages.get(self.current_page_id)
        return None

    def list_pages(self) -> List[str]:
        return list(self.pages.keys())

    def get_page(self, page_id: str) -> Optional[BrowserPage]:
        return self.pages.get(page_id)
