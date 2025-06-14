"""Browser automation tools using Playwright."""
from typing import Optional, Dict, Any, List, Union
import base64
import logging
from playwright.async_api import Page
from langchain.tools import tool

# Action recorder import
from ..agent.action_recorder_singleton import recorder

# Decorator to resolve hash arguments using element_map
import functools

def resolve_hash_args(tool_func):
    @functools.wraps(tool_func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        selector = kwargs.get("selector")
        # Always fetch the current page for DOMService
        from ..browser.page_manager import PageManager
        browser_page = PageManager.get_instance().get_current_page()
        dom_service = None
        if browser_page and hasattr(browser_page, "get_dom_service"):
            dom_service = browser_page.get_dom_service()
        # Only try to resolve if selector is a hash
        if selector and isinstance(selector, str) and selector.startswith("#") and dom_service:
            hash_val = selector
            logger.debug(f"Attempting to resolve hash selector: {hash_val} using DOMService")
            resolved = dom_service.resolve_selector_hash(hash_val)
            if not resolved:
                logger.error(f"Hash {hash_val} could not be resolved by DOMService.")
            else:
                logger.info(f"Resolved hash {hash_val} to selector: {resolved}")
                kwargs["selector"] = resolved
        else:
            logger.debug(f"Selector '{selector}' is not a hash, not present, or DOMService unavailable; skipping hash resolution.")
        return await tool_func(*args, **kwargs)
    wrapper._is_browser_tool = True
    return wrapper

# No global page reference; use BrowserPage abstraction moving forward.
# _page: Optional[Page] = None

from ..browser.page_manager import PageManager

@tool
@resolve_hash_args
async def get_all_elements(selector: str, attribute: str = "", **kwargs) -> str:
    """Get a list of text or attribute values for all elements matching the selector on the current browser page.
    Args:
        selector: CSS selector
        attribute: If provided, returns this attribute for each element; otherwise, returns text content.
    Returns:
        str: JSON list of values
    """
    import logging
    import json
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    logger.info(f"Getting all elements for selector '{selector}' on BrowserPage (url: {getattr(page, 'url', None)})")
    try:
        elements = await page.query_selector_all(selector)
        results = []
        for el in elements:
            if attribute:
                val = await el.get_attribute(attribute)
            else:
                val = await el.text_content()
            results.append(val or "")
        logger.info(f"Found {len(results)} elements for {selector}")
        recorder.record_action(
            tool="get_all_elements",
            args={"selector": selector, "attribute": attribute},
            command=f"await page.query_selector_all('{selector}')"
        )
        return json.dumps(results)
    except Exception as e:
        logger.error(f"Failed to get all elements for {selector}: {e}")
        return f"Error: {e}"

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
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return False
    page = browser_page.get_page()
    logger.info(f"Checking if element '{selector}' is enabled on BrowserPage (url: {getattr(page, 'url', None)})")
    try:
        el = await page.query_selector(selector)
        if not el:
            logger.warning(f"Element not found for {selector}")
            return False
        disabled = await el.get_attribute("disabled")
        enabled = disabled is None
        logger.info(f"Element {selector} enabled: {enabled}")
        recorder.record_action(
            tool="is_enabled",
            args={"selector": selector},
            command=f"await page.query_selector('{selector}').get_attribute('disabled')"
        )
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
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return 0
    page = browser_page.get_page()
    logger.info(f"Getting count for selector '{selector}' on BrowserPage (url: {getattr(page, 'url', None)})")
    try:
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

# set_page is deprecated in favor of passing BrowserPage explicitly.
# def set_page(page: Page) -> None:
#     """Set the Playwright page to use for browser interactions."""
#     global _page
#     _page = page
# New utility to get page and dom_service from BrowserPage

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
    recorder.record_action(
        tool="navigate",
        args={"url": url},
        command=f"await page.goto('{url}')"
    )
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
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        logger.info(f"Attempting to click {selector} (timeout={timeout}, force={force}) on BrowserPage (url: {getattr(page, 'url', None)})")
        locator = page.locator(selector)
        await locator.wait_for(state='visible', timeout=timeout)
        await locator.click(force=force)
        recorder.record_action(
            tool="click",
            args={"selector": selector, "timeout": timeout, "force": force},
            command=f"await page.locator('{selector}').click(force={force})"
        )
        logger.info(f"Clicked {selector}")
        return f"Clicked {selector}"
    except PlaywrightTimeoutError:
        error_msg = f"Timeout waiting for {selector} to be clickable."
        logger.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to click {selector}: {e}"
        logger.error(error_msg)
        # Take a screenshot to help with debugging
        try:
            import os
            os.makedirs('./screenshots', exist_ok=True)
            screenshot_path = f"./screenshots/click_error_{selector}.png"
            screenshot = await page.screenshot(path=screenshot_path, type='png')
            logger.debug(f"Screenshot saved to click_error_{selector}.png")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
        # Get page HTML for debugging
        try:
            html = await page.content()
            with open(f"click_error_{selector}.html", "w") as f:
                f.write(html)
            logger.debug(f"Page HTML saved to click_error_{selector}.html")
        except Exception as html_error:
            logger.error(f"Failed to save page HTML: {html_error}")
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
            locator = page.locator(f'xpath={selector}')
        else:
            locator = page.locator(selector)
        await locator.fill(text)
        logger.info(f"Filled field {selector} with text: {text} on BrowserPage (url: {page.url})")
        return f"Filled field {selector} with text: {text}"
    except Exception as e:
        error_msg = f"Failed to fill field {selector}: {str(e)}"
        logger.error(error_msg)
        # Take a screenshot to help with debugging
        try:
            import os
            os.makedirs('./screenshots', exist_ok=True)
            screenshot_path = f"./screenshots/click_error_{selector}.png"
            screenshot = await page.screenshot(path=screenshot_path, type='png')
            logger.debug(f"Screenshot taken after error and saved to {screenshot_path} (size: {len(screenshot)} bytes)")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
        return f"Error: {error_msg}"

@tool
async def list_interactive_elements() -> str:
    """List all interactive elements on the current browser page.
    Returns:
        str: Formatted string containing interactive elements and their details
    """
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        logger.info(f"Scanning page for interactive elements on BrowserPage (url: {getattr(page, 'url', None)})...")
        selectors = [
            'input:not([type="hidden"])',
            'button',
            'a',
            'select',
            'textarea',
            '[role="button"]',
            '[role="link"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[tabindex]:not([tabindex="-1"])'
        ]
        elements = []
        for selector in selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    elements.append(f"{selector} ({count} found)")
                    for i in range(min(3, count)):
                        try:
                            el = page.locator(selector).nth(i)
                            tag = await el.evaluate('el => el.tagName.toLowerCase()')
                            id_attr = await el.get_attribute('id') or ''
                            name_attr = await el.get_attribute('name') or ''
                            type_attr = await el.get_attribute('type') or ''
                            text = (await el.text_content() or '').strip()[:50]
                            details = []
                            if id_attr:
                                details.append(f"id={id_attr}")
                            if name_attr:
                                details.append(f"name={name_attr}")
                            if type_attr:
                                details.append(f"type={type_attr}")
                            if text:
                                details.append(f"text='{text}...'")
                            elements.append(f"  - {tag} {' '.join(details)}")
                        except Exception as e:
                            logger.debug(f"Error getting details for element {i} of {selector}: {str(e)}")
                            continue
            except Exception as e:
                logger.debug(f"Error counting elements for {selector}: {str(e)}")
                continue
        if not elements:
            return "No interactive elements found on the page."
        result = ["Interactive elements found on the page:", ""]
        result.extend(elements)
        # Take a screenshot for reference
        try:
            import os
            os.makedirs('./screenshots', exist_ok=True)
            screenshot_path = f"./screenshots/list_interactive_elements_{selector if 'selector' in locals() else 'page'}.png"
            screenshot = await page.screenshot(path=screenshot_path, type='png')
            logger.debug(f"Page screenshot taken and saved to {screenshot_path} (size: {len(screenshot)} bytes)")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
        return "\n".join(result)
    except Exception as e:
        error_msg = f"Failed to list interactive elements: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"
