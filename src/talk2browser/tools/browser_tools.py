"""Browser automation tools using Playwright."""
from typing import Optional, Dict, Any, List, Union
import base64
import logging
from playwright.async_api import Page
from langchain.tools import tool

# Action recorder singleton import (shared across modules)

import logging


# Decorator to resolve hash arguments using element_map
import functools

# --- Selector Normalization Utility ---
def normalize_selector(selector: str, logger=None) -> str:
    """
    Convert jQuery-style :contains("text") selectors to Playwright-compatible text selectors.
    Examples:
      - 'div:contains("Text")' -> 'div >> text="Text"'
      - ':contains("Text")' -> 'text="Text"'
    """
    import re
    if not selector or not isinstance(selector, str):
        return selector
    pattern = r'^(?P<tag>\w+)?\s*:contains\(["\\'](?P<text>.+)["\\']\)$'
    match = re.match(pattern, selector.strip())
    if match:
        tag = match.group('tag')
        text = match.group('text')
        new_selector = f'{tag} >> text="{text}"' if tag else f'text="{text}"'
        if logger:
            logger.debug(f"Normalized selector: '{selector}' -> '{new_selector}'")
        return new_selector
    return selector

# --- Centralized Screenshot Utility for User Actions ---
async def capture_screenshot_for_action(page, tool_name: str, logger, success=True) -> Optional[str]:
    """
    Capture a screenshot for user actions, save it with a consistent name, and return the path.
    Args:
        page: Playwright Page object
        tool_name: Name of the tool/action (str)
        logger: Logger instance
        success: Whether the action succeeded (bool)
    Returns:
        str: Path to the screenshot, or None if failed
    """
    try:
        from pathlib import Path
        base_name = "step"
        status = "success" if success else "fail"
        screenshot_path = str(Path("./generated") / f"{base_name}_{tool_name}_{status}.png")
        logger.debug(f"Attempting to save screenshot for action {tool_name} at {screenshot_path}")
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"Screenshot saved to {screenshot_path} for {tool_name} (success={success})")
        return screenshot_path
    except Exception as e:
        logger.error(f"Failed to capture screenshot for {tool_name}: {e}")
        return None

def resolve_hash_args(tool_func):
    @functools.wraps(tool_func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        selector = kwargs.get("selector")
        from ..browser.page_manager import PageManager
        browser_page = PageManager.get_instance().get_current_page()
        dom_service = None
        if browser_page and hasattr(browser_page, "get_dom_service"):
            dom_service = browser_page.get_dom_service()
        logger.info(
            f"TOOL PARAMS: {tool_func.__name__} called with selector={selector}, browser_page={browser_page}, dom_service={dom_service}"
        )
        # Only try to resolve if selector is a hash
        if selector and isinstance(selector, str) and selector.startswith("#") and dom_service:
            hash_val = selector
            logger.info(f"Attempting to resolve hash selector: {hash_val} using DOMService")
            resolved = dom_service.resolve_selector_hash(hash_val)
            if not resolved:
                logger.error(f"Hash {hash_val} could not be resolved by DOMService.")
            else:
                logger.info(f"Resolved hash {hash_val} to selector: {resolved}")
                kwargs["selector"] = resolved
        else:
            logger.info(
                f"Selector '{selector}' is not a hash, not present, or DOMService unavailable; skipping hash resolution."
            )
        return await tool_func(*args, **kwargs)
    wrapper._is_browser_tool = True
    return wrapper

# No global page reference; use BrowserPage abstraction moving forward.
# _page: Optional[Page] = None

from ..browser.page_manager import PageManager


@tool
@resolve_hash_args
async def is_enabled(selector: str, **kwargs) -> bool:
    """Check if an element is enabled (not disabled) on the current browser page.
    Args:
        selector: CSS selector
    Returns:
        bool: True if enabled, False if disabled or not found
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: is_enabled(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return False
    page = browser_page.get_page()
    logger.info(f"Checking if element '{selector}' is enabled on BrowserPage (url: {getattr(page, 'url', None)})")
    try:
        selector = normalize_selector(selector, logger)
        el = await page.query_selector(selector)
        if not el:
            logger.warning(f"Element not found for {selector}")
            return False
        disabled = await el.get_attribute("disabled")
        enabled = disabled is None
        logger.info(f"Element {selector} enabled: {enabled}")
        from ..services.action_service import ActionService
        action_data = {
            "type": "is_enabled",
            "args": {"selector": selector},
            "result": enabled
        }
        ActionService.get_instance().record_agent_action(action_data)
        return enabled
    except Exception as e:
        logger.error(f"Failed to check enabled for {selector}: {e}")
        
        return False

@tool
@resolve_hash_args
async def get_count(selector: str, **kwargs) -> int:
    """Return the number of elements matching the selector on the current browser page.
    Args:
        selector: CSS selector
    Returns:
        int: Number of elements found
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: get_count(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return 0
    page = browser_page.get_page()
    logger.info(f"Getting count for selector '{selector}' on BrowserPage (url: {getattr(page, 'url', None)})")
    try:
        # Normalize selector before using it
        selector = normalize_selector(selector, logger)
        elements = await page.query_selector_all(selector)
        count = len(elements)
        logger.info(f"Found {count} elements for {selector}")
        recorder.record_action(
            tool="get_count",
            args={"selector": selector},
            command=f"len(await page.query_selector_all('{selector}'))"
        )
        
        return count
    except Exception as e:
        logger.error(f"Failed to get count for {selector}: {e}")
        
        return 0

@tool
async def navigate(url: str) -> str:
    """Navigate to a URL using the current browser page.
    Args:
        url: The URL to navigate to
    Returns:
        str: Confirmation message with the loaded URL and page title
    """
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    logger.info(f"Navigating BrowserPage (url before: {getattr(page, 'url', None)}) to {url}")
    await page.goto(url)
    title = await page.title()
    from ..services.action_service import ActionService
    screenshot_path = await capture_screenshot_for_action(page, "navigate", logger, success=True)
    action_data = {
        "type": "navigate",
        "args": {"url": url},
        "screenshot": screenshot_path
    }
    ActionService.get_instance().record_agent_action(action_data)
    logger.info(f"Navigated to {url}. Page title: {title}")
    return f"Navigated to {url}. Page title: {title}"

@tool
@resolve_hash_args
async def click(selector: str, *, timeout: int = 5000, element_map: dict = None) -> str:
    """Click on an element matching the CSS selector on the current browser page.
    Args:
        selector: CSS selector of the element to click
        timeout: Maximum time to wait for the element to be clickable (ms)
    Returns:
        str: Confirmation message with the clicked element or error details
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: click(selector={selector}, timeout={timeout}, element_map={element_map})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Detect XPath and prefix as needed
        orig_selector = selector
        if selector.startswith('/') or selector.startswith('html/'):
            selector = f"xpath={selector}"
            logger.debug(f"Selector '{orig_selector}' looks like XPath, transformed to '{selector}' for Playwright locator.")
        else:
            logger.debug(f"Selector '{selector}' used as-is for Playwright locator.")
        logger.info(f"Attempting to click {selector} (timeout={timeout}) on BrowserPage (url: {getattr(page, 'url', None)})")
        locator = page.locator(selector)
        await locator.wait_for(state='visible', timeout=timeout)
        await locator.click()
        recorder.record_action(
            tool="click",
            args={"selector": selector, "timeout": timeout},
            command=f"await page.locator('{selector}').click()"
        )
        await capture_and_record_screenshot(page, "click", logger, recorder, success=True)
        logger.info(f"Clicked {selector}")
        return f"Clicked {selector}"
    except PlaywrightTimeoutError:
        error_msg = f"Timeout waiting for {selector} to be clickable."
        logger.error(error_msg)
        await capture_and_record_screenshot(page, "click", logger, recorder, success=False)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to click {selector}: {e}"
        logger.error(error_msg)
        await capture_and_record_screenshot(page, "click", logger, recorder, success=False)
        return f"Error: {error_msg}"

@tool
@resolve_hash_args
async def fill(selector: str, text: str, **kwargs) -> str:
    """Fill a form field with the specified text on the current browser page.
    Args:
        selector: CSS selector of the input field
        text: Text to fill in the field
    Returns:
        str: Confirmation message or error details
    """
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: fill(selector={selector}, text={text}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        logger.info(f"Attempting to fill field {selector} with text: {text} on BrowserPage (url: {getattr(page, 'url', None)})")
        # If selector looks like an XPath, prefix with 'xpath=' for Playwright
        if selector.startswith('/') or selector.startswith('html/'):
            xpath = selector
            locator = page.locator(f'xpath={selector}')
        else:
            xpath = None
            locator = page.locator(selector)
        try:
            await locator.fill(text)
            logger.info(f"Filled field {selector} with text: {text} on BrowserPage (url: {page.url})")
            recorder.record_action(tool="fill", args={"selector": selector, "text": text}, command=f"await page.locator('{selector}').fill('{text}')")
            await capture_and_record_screenshot(page, "fill", logger, recorder, success=True)
            return f"Filled field {selector} with text: {text}"
        finally:
            if xpath:
                # Explicitly fetch dom_service in local scope for finally block
                dom_service = None
                if browser_page and hasattr(browser_page, "get_dom_service"):
                    dom_service = browser_page.get_dom_service()
                    logger.debug(f"Fetched dom_service in finally block: {dom_service}")

    except Exception as e:
        error_msg = f"Failed to fill field {selector}: {str(e)}"
        logger.error(error_msg)
        await capture_and_record_screenshot(page, "fill", logger, recorder, success=False)
        await handle_tool_exception(page, selector, error_msg, logger)
        return f"Error: {error_msg}"

@tool
@resolve_hash_args
async def type(selector: str, text: str, **kwargs) -> str:
    """Type text into an element, simulating key events (unlike fill)."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: type(selector={selector}, text={text}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        locator = page.locator(selector)
        await locator.type(text)
        logger.info(f"Typed '{text}' into {selector}")
        recorder.record_action(tool="type", args={"selector": selector, "text": text}, command=f"await page.locator('{selector}').type('{text}')")
        await capture_and_record_screenshot(page, "type", logger, recorder, success=True)
        return f"Typed '{text}' into {selector}"
    except Exception as e:
        logger.error(f"Failed to type into {selector}: {e}")
        await capture_and_record_screenshot(page, "type", logger, recorder, success=False)
        return f"Error: Failed to type into {selector}: {e}"

@tool
@resolve_hash_args
async def check(selector: str, **kwargs) -> str:
    """Check a checkbox or radio button."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: check(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        locator = page.locator(selector)
        await locator.check()
        logger.info(f"Checked {selector}")
        recorder.record_action(tool="check", args={"selector": selector}, command=f"await page.locator('{selector}').check()")
        await capture_and_record_screenshot(page, "check", logger, recorder, success=True)
        return f"Checked {selector}"
    except Exception as e:
        logger.error(f"Failed to check {selector}: {e}")
        await capture_and_record_screenshot(page, "check", logger, recorder, success=False)
        return f"Error: Failed to check {selector}: {e}"

@tool
@resolve_hash_args
async def uncheck(selector: str, **kwargs) -> str:
    """Uncheck a checkbox."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: uncheck(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        locator = page.locator(selector)
        await locator.uncheck()
        logger.info(f"Unchecked {selector}")
        recorder.record_action(tool="uncheck", args={"selector": selector}, command=f"await page.locator('{selector}').uncheck()")
        await capture_and_record_screenshot(page, "uncheck", logger, recorder, success=True)
        return f"Unchecked {selector}"
    except Exception as e:
        logger.error(f"Failed to uncheck {selector}: {e}")
        await capture_and_record_screenshot(page, "uncheck", logger, recorder, success=False)
        return f"Error: Failed to uncheck {selector}: {e}"

@tool
@resolve_hash_args
async def select_option(selector: str, value: str, **kwargs) -> str:
    """Select an option in a <select> element."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: select_option(selector={selector}, value={value}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        locator = page.locator(selector)
        await locator.select_option(value)
        logger.info(f"Selected option '{value}' in {selector}")
        recorder.record_action(tool="select_option", args={"selector": selector, "value": value}, command=f"await page.locator('{selector}').select_option('{value}')")
        await capture_and_record_screenshot(page, "select_option", logger, recorder, success=True)
        return f"Selected option '{value}' in {selector}"
    except Exception as e:
        logger.error(f"Failed to select option in {selector}: {e}")
        await capture_and_record_screenshot(page, "select_option", logger, recorder, success=False)
        return f"Error: Failed to select option in {selector}: {e}"

@tool
@resolve_hash_args
async def hover(selector: str, **kwargs) -> str:
    """Hover over an element."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: hover(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        locator = page.locator(selector)
        selector = normalize_selector(selector, logger)
        await locator.hover()
        logger.info(f"Hovered over {selector}")
        recorder.record_action(tool="hover", args={"selector": selector}, command=f"await page.locator('{selector}').hover()")
        
        return f"Hovered over {selector}"
    except Exception as e:
        logger.error(f"Failed to hover over {selector}: {e}")
        
        return f"Error: Failed to hover over {selector}: {e}"

@tool
@resolve_hash_args
async def wait_for_selector(selector: str, state: str = "visible", timeout: int = 5000, **kwargs) -> str:
    """Wait for a selector to reach a certain state (visible, attached, detached, hidden)."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: wait_for_selector(selector={selector}, state={state}, timeout={timeout}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        locator = page.locator(selector)
        selector = normalize_selector(selector, logger)
        await locator.wait_for(state=state, timeout=timeout)
        logger.info(f"Waited for {selector} to be {state}")
        recorder.record_action(tool="wait_for_selector", args={"selector": selector, "state": state, "timeout": timeout}, command=f"await page.locator('{selector}').wait_for(state='{state}', timeout={timeout})")
        try:
            from pathlib import Path
            action_idx = len(recorder.actions) - 1
            base_name = recorder.base_name or "step"
            screenshot_path = str(Path("./generated") / f"{base_name}_step{action_idx}_wait_for_selector.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            recorder.update_screenshot_path(action_idx, screenshot_path)
            logger.debug(f"Screenshot saved to {screenshot_path} for wait_for_selector action.")
        except Exception as e:
            logger.error(f"Failed to save screenshot after wait_for_selector: {e}")
        return f"Waited for {selector} to be {state}"
    except Exception as e:
        logger.error(f"Failed to wait for {selector}: {e}")
        return f"Error: Failed to wait for {selector}: {e}"

@tool
async def screenshot(selector: str = None, path: str = None, **kwargs) -> str:
    """Take a screenshot of the current page or a specific element. If selector is None, capture the full page."""
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: screenshot(selector={selector}, path={path}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        if selector:
            selector = normalize_selector(selector, logger)
            locator = page.locator(selector)
            await locator.screenshot(path=path)
            logger.info(f"Screenshot taken of {selector} at {path}")
            recorder.record_action(tool="screenshot", args={"selector": selector, "path": path}, command=f"await page.locator('{selector}').screenshot(path='{path}')")
        else:
            await page.screenshot(path=path, full_page=True)
            logger.info(f"Full page screenshot taken at {path}")
            recorder.record_action(tool="screenshot", args={"selector": None, "path": path}, command=f"await page.screenshot(path='{path}', full_page=True)")
        return f"Screenshot taken at {path}"
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return f"Error: Failed to take screenshot: {e}"

# Not an LLM tool. Used internally by DOM service.
async def list_interactive_elements() -> str:
    """List interactive elements on the page. (Internal service, not an LLM tool.)"""
    pass


# --- LLM Tool: Generate PDF from HTML ---
from langchain.tools import tool

@tool
def generate_pdf_from_html(html: str, path: str = None) -> str:
    """Generate a PDF from HTML content using Playwright. Args: html (str): HTML content. path (str, optional): Output PDF path. Returns: str: Path to the generated PDF or error message."""
    import logging
    import asyncio
    from pathlib import Path
    from datetime import datetime
    from playwright.async_api import async_playwright

    logger = logging.getLogger(__name__)
    logger.info("TOOL CALL: generate_pdf_from_html() called")
    async def _generate():
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html)
                output_path = path
                if not output_path:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_path = str(Path("./generated") / f"generated_pdf_{timestamp}.pdf")
                await page.pdf(path=output_path)
                await browser.close()
                logger.info(f"PDF generated at {output_path}")
                if recorder:
                    recorder.record_action(tool="generate_pdf_from_html", args={"html": "<omitted>", "path": output_path}, command=f"await page.pdf(path='{output_path}')")
                return output_path
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            return f"Error: Failed to generate PDF: {e}"
    return asyncio.run(_generate())
