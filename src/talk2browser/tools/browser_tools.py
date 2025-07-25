"""Browser automation tools using Playwright."""

from typing import Optional
from langchain.tools import tool
import logging
from ..services.action_service import ActionService
from ..browser.page_manager import PageManager
from langchain.tools import tool as langchain_tool

# Action recorder singleton import (shared across modules)
import functools


# --- Selector Normalization Utility ---
def normalize_selector(selector: str, logger=None) -> str:
    """
    Normalize selectors for Playwright compatibility:
    1. Convert jQuery-style :contains("text") selectors to Playwright text selectors
       - 'div:contains("Text")' -> 'div >> text="Text"'
       - ':contains("Text")' -> 'text="Text"'
    2. Detect XPath selectors and prefix them with 'xpath='
       - '/html/body/div[1]' -> 'xpath=/html/body/div[1]'
       - 'html/body/div[1]' -> 'xpath=html/body/div[1]'
    """
    import re

    if not selector or not isinstance(selector, str):
        return selector

    # Already normalized with xpath= prefix
    if selector.startswith("xpath="):
        return selector

    # Case 1: jQuery :contains() selector
    pattern = r'^(?P<tag>\w+)?\s*:contains\(["\'](?P<text>.+)["\']\)$'
    match = re.match(pattern, selector.strip())
    if match:
        tag = match.group("tag")
        text = match.group("text")
        new_selector = f'{tag} >> text="{text}"' if tag else f'text="{text}"'
        if logger:
            logger.debug(
                f"Normalized jQuery selector: '{selector}' -> '{new_selector}'"
            )
        return new_selector

    # Case 2: XPath-like selector
    # XPath patterns typically start with / or contain element/element patterns
    xpath_pattern = r"^(/|html/|body/|//|\w+/\w+/)"
    if re.match(xpath_pattern, selector.strip()) or selector.count("/") > 1:
        new_selector = f"xpath={selector}"
        if logger:
            logger.debug(f"Detected XPath selector: '{selector}' -> '{new_selector}'")
        return new_selector

    return selector


# --- Centralized Screenshot Utility for User Actions ---
async def capture_screenshot_for_action(
    page, tool_name: str, logger, success=True
) -> Optional[str]:
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
        # Always save screenshots to ./screenshots directory
        screenshots_dir = Path("./screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = str(
            screenshots_dir / f"{base_name}_{tool_name}_{status}_{timestamp}.png"
        )
        logger.debug(
            f"Attempting to save screenshot for action {tool_name} at {screenshot_path}"
        )
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(
            f"Screenshot saved to {screenshot_path} for {tool_name} (success={success})"
        )
        return screenshot_path
    except Exception as e:
        logger.error(f"Failed to capture screenshot for {tool_name}: {e}")
        return None


def resolve_secret_args(tool_func):
    import functools
    from ..utils.secret_resolver import resolve_secret_placeholders
    import logging

    @functools.wraps(tool_func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        # Remove sensitive_data from kwargs if present
        kwargs.pop("sensitive_data", None)
        # Resolve secrets in all string args/kwargs
        logger.debug(f"[resolve_secret_args] BEFORE: args={args}, kwargs={kwargs}")
        new_args = [
            resolve_secret_placeholders(arg) if isinstance(arg, str) else arg
            for arg in args
        ]
        new_kwargs = {
            k: resolve_secret_placeholders(v) if isinstance(v, str) else v
            for k, v in kwargs.items()
        }
        logger.debug(
            f"[resolve_secret_args] AFTER: new_args={new_args}, new_kwargs={new_kwargs}"
        )
        # Warn if any string arg/kwarg still looks like a secret placeholder
        for idx, val in enumerate(new_args):
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                logger.warning(
                    f"[resolve_secret_args] Unresolved secret placeholder in args[{idx}]: {val}"
                )
        for k, v in new_kwargs.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                logger.warning(
                    f"[resolve_secret_args] Unresolved secret placeholder in kwargs['{k}']: {v}"
                )
        return await tool_func(*new_args, **new_kwargs)

    return wrapper


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
        if (
            selector
            and isinstance(selector, str)
            and selector.startswith("#")
            and dom_service
        ):
            hash_val = selector
            logger.info(
                f"Attempting to resolve hash selector: {hash_val} using DOMService"
            )
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


@tool
@resolve_hash_args
async def is_enabled(selector: str, **kwargs) -> bool:
    """Check if an element is enabled (not disabled) on the current browser page.
    Args:
        selector: CSS selector
    Returns:
        bool: True if enabled, False if disabled or not found
    """
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    logger = logging.getLogger(__name__)
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting is_enabled.")
        return False
    logger.info(f"TOOL CALL: is_enabled(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return False
    page = browser_page.get_page()
    logger.info(
        f"Checking if element '{selector}' is enabled on BrowserPage (url: {getattr(page, 'url', None)})"
    )
    try:
        selector = normalize_selector(selector, logger)
        el = await page.query_selector(selector)
        if not el:
            logger.warning(f"Element not found for {selector}")
            return False
        disabled = await el.get_attribute("disabled")
        enabled = disabled is None
        logger.info(f"Element {selector} enabled: {enabled}")

        action_data = {
            "type": "is_enabled",
            "args": {"selector": selector},
            "result": enabled,
        }
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after is_enabled: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after is_enabled: {ActionService.get_instance().actions}"
        )
        return enabled
    except Exception as e:
        logger.error(f"Failed to check enabled for {selector}: {e}")
        return False


@tool
@resolve_hash_args
async def resolve_selector(selector, dom_service, logger):
    """
    Resolves a hash selector to an XPath selector using DOMService if needed.
    Returns a valid Playwright selector (xpath=...), or the original if not a hash.
    """
    if (
        selector
        and isinstance(selector, str)
        and selector.startswith("#")
        and dom_service
    ):
        xpath = dom_service.hash_to_xpath(selector)
        if xpath:
            resolved = f"xpath={xpath}"
            if logger:
                logger.info(f"Resolved hash {selector} to selector: {resolved}")
            return resolved
        else:
            if logger:
                logger.error(f"Could not resolve hash selector: {selector}")
            return None
    return selector


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
    logger.info(
        f"Getting count for selector '{selector}' on BrowserPage (url: {getattr(page, 'url', None)})"
    )
    try:
        # Normalize selector before using it
        selector = normalize_selector(selector, logger)
        elements = await page.query_selector_all(selector)
        count = len(elements)
        logger.info(f"Found {count} elements for {selector}")

        action_data = {"type": "get_count", "args": {"selector": selector}}
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after get_count: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after get_count: {ActionService.get_instance().actions}"
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
    logger.info(
        f"Navigating BrowserPage (url before: {getattr(page, 'url', None)}) to {url}"
    )
    await page.goto(url, wait_until="networkidle")
    logger.info(f"Navigated to {url}")
    # --- Screenshot capture after navigation ---
    screenshot_path = await capture_screenshot_for_action(page, "navigate", logger)
    if screenshot_path:

        ActionService.get_instance().record_screenshot(screenshot_path)
    title = await page.title()
    import os

    screenshot_path = None
    if (
        os.getenv("T2B_SCREENSHOT_TO_LLM", "0") == "1"
        or os.getenv("T2B_SCREENSHOT_EVERY_STEP", "0") == "1"
    ):
        screenshot_path = await capture_screenshot_for_action(
            page, "navigate", logger, success=True
        )
    action_data = {"type": "navigate", "args": {"url": url}}
    if screenshot_path:
        action_data["screenshot_path"] = screenshot_path
        logger.debug(
            f"[browser_tools/navigate] Screenshot for LLM vision: {screenshot_path}"
        )
    ActionService.get_instance().record_agent_action(action_data)
    logger.debug(
        f"[browser_tools] Agent actions after navigate: {ActionService.get_instance().agent_actions}"
    )
    logger.debug(
        f"[browser_tools] Merged actions after navigate: {ActionService.get_instance().actions}"
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
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting click.")
        return "Error: Selector could not be resolved."
    logger.info(
        f"TOOL CALL: click(selector={selector}, timeout={timeout}, element_map={element_map})"
    )
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        else:
            logger.debug(f"Selector '{selector}' used as-is for Playwright locator.")
        logger.info(
            f"Attempting to click {selector} (timeout={timeout}) on BrowserPage (url: {getattr(page, 'url', None)})"
        )
        locator = page.locator(selector)
        await locator.wait_for(state="visible", timeout=timeout)
        await locator.click()

        # Standardize selector and add selector_type
        if (
            selector.startswith("/")
            or selector.startswith("html/")
            or selector.startswith("//")
        ):
            std_selector = (
                f"xpath={selector}" if not selector.startswith("xpath=") else selector
            )
            selector_type = "xpath"
        else:
            std_selector = selector
            selector_type = "css"
        # --- Ensure selector hash is resolved and included in args for ActionService ---
        hash_val = None
        if browser_page and hasattr(browser_page, "get_dom_service"):
            dom_service = browser_page.get_dom_service()
            if dom_service:
                # Try to resolve hash from selector
                if selector and isinstance(selector, str):
                    if selector.startswith("#"):
                        hash_val = selector
                    else:
                        element_map = getattr(dom_service, "_element_map", {})
                        for h, sel in element_map.items():
                            if sel == selector:
                                hash_val = h
                                break
        logger.debug(f"[click] Resolved hash for selector '{selector}': {hash_val}")
        args = {
            "selector": std_selector,
            "selector_type": selector_type,
            "timeout": timeout,
        }
        if hash_val:
            args["hash"] = hash_val
        action_data = {"type": "click", "args": args}
        ActionService.get_instance().record_agent_action(action_data)
        logger.info(f"[click] Recorded click action: {action_data}")
        logger.debug(
            f"[browser_tools] Agent actions after click: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after click: {ActionService.get_instance().actions}"
        )
        import os

        screenshot_path = None
        if (
            os.getenv("T2B_SCREENSHOT_TO_LLM", "0") == "1"
            or os.getenv("T2B_SCREENSHOT_EVERY_STEP", "0") == "1"
        ):
            screenshot_path = await capture_screenshot_for_action(
                page, "click", logger, success=True
            )
            if screenshot_path:
                action_data["screenshot_path"] = screenshot_path
                logger.debug(
                    f"[browser_tools/click] Screenshot for LLM vision: {screenshot_path}"
                )
        if screenshot_path:
            try:
                from ..services.vision_service import VisionService
                from ..utils.config import is_vision_enabled

                if is_vision_enabled():
                    vision_results = VisionService.get_instance().analyze(
                        screenshot_path
                    )
                    logger.debug(
                        f"[browser_tools/click] Vision results for {screenshot_path}: {vision_results}"
                    )
            except Exception as e:
                logger.error(f"[browser_tools/click] VisionService error: {e}")
        logger.info(f"Clicked {selector}")
        return f"Clicked {selector}"
    except PlaywrightTimeoutError:
        error_msg = f"Timeout waiting for {selector} to be clickable."
        logger.error(error_msg)
        await capture_screenshot_for_action(page, "click", logger, success=False)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to click {selector}: {e}"
        logger.error(error_msg)
        await capture_screenshot_for_action(page, "click", logger, success=False)
        return f"Error: {error_msg}"


@tool
@resolve_secret_args
@resolve_hash_args
async def fill(selector: str, text: str, **kwargs) -> str:
    """
    Fill a form field with the specified text on the current browser page.

    Use this tool for standard HTML input fields (e.g., <input>, <textarea>, login/password forms).
    DO NOT use this tool for code editors like Ace, Monaco, or CodeMirror—use 'set_code_in_editor' for those.

    Args:
        selector: CSS selector of the input field
        text: Text to fill in the field
    Returns:
        str: Confirmation message or error details
    """
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting fill.")
        return "Error: Selector could not be resolved."
    logger.info(f"TOOL CALL: fill(selector={selector}, text={text}, kwargs={kwargs})")
    # Assert that text is not a secret placeholder
    if isinstance(text, str) and text.startswith("${") and text.endswith("}"):
        logger.error(f"[fill] Secret placeholder was not resolved: {text}")
        raise ValueError(f"[fill] Secret placeholder was not resolved: {text}")
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        logger.info(
            f"Attempting to fill field {selector} with text: {text} on BrowserPage (url: {getattr(page, 'url', None)})"
        )
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        # Store original xpath for reference if needed
        xpath = orig_selector if selector.startswith("xpath=") else None
        locator = page.locator(selector)
        try:
            await locator.fill(text)
            logger.info(f"Filled element {selector} with text: {text}")
            # --- Screenshot capture after fill ---
            screenshot_path = await capture_screenshot_for_action(page, "fill", logger)
            if screenshot_path:

                ActionService.get_instance().record_screenshot(screenshot_path)
            logger.info(
                f"Filled field {selector} with text: {text} on BrowserPage (url: {page.url})"
            )

            # --- Ensure selector hash is resolved and included in args for ActionService ---
            hash_val = None
            if browser_page and hasattr(browser_page, "get_dom_service"):
                dom_service = browser_page.get_dom_service()
                if dom_service:
                    # Try to resolve hash from selector
                    if selector and isinstance(selector, str):
                        if selector.startswith("#"):
                            hash_val = selector
                        else:
                            # Try to find hash for this selector in DOMService
                            element_map = getattr(dom_service, "_element_map", {})
                            for h, sel in element_map.items():
                                if sel == selector:
                                    hash_val = h
                                    break
            logger.debug(f"[fill] Resolved hash for selector '{selector}': {hash_val}")
            # Standardize selector and add selector_type
            if (
                selector.startswith("/")
                or selector.startswith("html/")
                or selector.startswith("//")
            ):
                std_selector = (
                    f"xpath={selector}"
                    if not selector.startswith("xpath=")
                    else selector
                )
                selector_type = "xpath"
            else:
                std_selector = selector
                selector_type = "css"
            args = {
                "selector": std_selector,
                "selector_type": selector_type,
                "text": text,
            }
            if hash_val:
                args["hash"] = hash_val
            action_data = {"type": "fill", "args": args}

            ActionService.get_instance().record_agent_action(action_data)
            logger.info(f"[fill] Recorded fill action: {action_data}")
            logger.debug(
                f"[browser_tools] Agent actions after fill: {ActionService.get_instance().agent_actions}"
            )
            logger.debug(
                f"[browser_tools] Merged actions after fill: {ActionService.get_instance().actions}"
            )
            dom_service = None
            if browser_page and hasattr(browser_page, "get_dom_service"):
                dom_service = browser_page.get_dom_service()
                logger.debug(f"Fetched dom_service in finally block: {dom_service}")
            import os

            screenshot_path = None
            if (
                os.getenv("T2B_SCREENSHOT_TO_LLM", "0") == "1"
                or os.getenv("T2B_SCREENSHOT_EVERY_STEP", "0") == "1"
            ):
                screenshot_path = await capture_screenshot_for_action(
                    page, "fill", logger, success=True
                )
                if screenshot_path:
                    action_data["screenshot_path"] = screenshot_path
                    logger.debug(
                        f"[browser_tools/fill] Screenshot for LLM vision: {screenshot_path}"
                    )
            if screenshot_path:
                try:
                    from ..services.vision_service import VisionService
                    from ..utils.config import is_vision_enabled

                    if is_vision_enabled():
                        vision_results = VisionService.get_instance().analyze(
                            screenshot_path
                        )
                        logger.debug(
                            f"[browser_tools/fill] Vision results for {screenshot_path}: {vision_results}"
                        )
                except Exception as e:
                    logger.error(f"[browser_tools/fill] VisionService error: {e}")
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
        from .handle_tool_exception import handle_tool_exception

        return await handle_tool_exception(
            page, selector, error_msg, logger, screenshot_prefix="fill"
        )


@tool
@resolve_hash_args
async def type(selector: str, text: str, **kwargs) -> str:
    """Type text into an element, simulating key events (unlike fill)."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting type.")
        return "Error: Selector could not be resolved."
    logger.info(f"TOOL CALL: type(selector={selector}, text={text}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        locator = page.locator(selector)
        await locator.type(text)
        logger.info(f"Typed '{text}' into {selector}")
        # --- Screenshot capture after type ---
        screenshot_path = await capture_screenshot_for_action(page, "type", logger)
        if screenshot_path:

            ActionService.get_instance().record_screenshot(screenshot_path)

        action_data = {"type": "type", "args": {"selector": selector, "text": text}}
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after type: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after type: {ActionService.get_instance().actions}"
        )
        screenshot_path = await capture_screenshot_for_action(
            page, "type", logger, success=True
        )
        if screenshot_path:
            try:
                from ..services.vision_service import VisionService
                from ..utils.config import is_vision_enabled

                if is_vision_enabled():
                    vision_results = VisionService.get_instance().analyze(
                        screenshot_path
                    )
                    logger.debug(
                        f"[browser_tools/type] Vision results for {screenshot_path}: {vision_results}"
                    )
            except Exception as e:
                logger.error(f"[browser_tools/type] VisionService error: {e}")
        return f"Typed '{text}' into {selector}"
    except Exception as e:
        logger.error(f"Failed to type into {selector}: {e}")
        await capture_screenshot_for_action(page, "type", logger, success=False)
        return f"Error: Failed to type into {selector}: {e}"


@tool
@resolve_hash_args
async def check(selector: str, **kwargs) -> str:
    """Check a checkbox or radio button."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting check.")
        return "Error: Selector could not be resolved."
    logger.info(f"TOOL CALL: check(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        locator = page.locator(selector)
        await locator.check()
        logger.info(f"Checked {selector}")

        action_data = {"type": "check", "args": {"selector": selector}}
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after check: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after check: {ActionService.get_instance().actions}"
        )
        await capture_screenshot_for_action(page, "check", logger, success=True)
        return f"Checked {selector}"
    except Exception as e:
        logger.error(f"Failed to check {selector}: {e}")
        await capture_screenshot_for_action(page, "check", logger, success=False)
        return f"Error: Failed to check {selector}: {e}"


@tool
@resolve_hash_args
async def uncheck(selector: str, **kwargs) -> str:
    """Uncheck a checkbox."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting uncheck.")
        return "Error: Selector could not be resolved."
    logger.info(f"TOOL CALL: uncheck(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        locator = page.locator(selector)
        await locator.uncheck()
        logger.info(f"Unchecked {selector}")

        action_data = {"type": "uncheck", "args": {"selector": selector}}
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after uncheck: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after uncheck: {ActionService.get_instance().actions}"
        )
        await capture_screenshot_for_action(page, "uncheck", logger, success=True)
        return f"Unchecked {selector}"
    except Exception as e:
        logger.error(f"Failed to uncheck {selector}: {e}")
        await capture_screenshot_for_action(page, "uncheck", logger, success=False)
        return f"Error: Failed to uncheck {selector}: {e}"


@tool
@resolve_hash_args
async def select_option(selector: str, value: str, **kwargs) -> str:
    """Select an option in a <select> element."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting select_option.")
        return "Error: Selector could not be resolved."
    logger.info(
        f"TOOL CALL: select_option(selector={selector}, value={value}, kwargs={kwargs})"
    )
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        locator = page.locator(selector)
        await locator.select_option(value)
        logger.info(f"Selected option '{value}' in {selector}")

        action_data = {
            "type": "select_option",
            "args": {"selector": selector, "value": value},
        }
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after select_option: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after select_option: {ActionService.get_instance().actions}"
        )
        await capture_screenshot_for_action(page, "select_option", logger, success=True)
        return f"Selected option '{value}' in {selector}"
    except Exception as e:
        logger.error(f"Failed to select option in {selector}: {e}")
        await capture_screenshot_for_action(
            page, "select_option", logger, success=False
        )
        return f"Error: Failed to select option in {selector}: {e}"


@tool
@resolve_hash_args
async def hover(selector: str, **kwargs) -> str:
    """Hover over an element."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting hover.")
        return "Error: Selector could not be resolved."
    logger.info(f"TOOL CALL: hover(selector={selector}, kwargs={kwargs})")
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        locator = page.locator(selector)
        await locator.hover()
        logger.info(f"Hovered over {selector}")

        action_data = {"type": "hover", "args": {"selector": selector}}
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after hover: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after hover: {ActionService.get_instance().actions}"
        )
        return f"Hovered over {selector}"
    except Exception as e:
        logger.error(f"Failed to hover over {selector}: {e}")
        return f"Error: Failed to hover over {selector}: {e}"


@tool
@resolve_hash_args
async def wait_for_selector(
    selector: str, state: str = "visible", timeout: int = 5000, **kwargs
) -> str:
    """Wait for a selector to reach a certain state (visible, attached, detached, hidden)."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    selector = resolve_selector(selector, dom_service, logger)
    if not selector:
        logger.error("Selector could not be resolved. Aborting wait_for_selector.")
        return "Error: Selector could not be resolved."
    logger.info(
        f"TOOL CALL: wait_for_selector(selector={selector}, state={state}, timeout={timeout}, kwargs={kwargs})"
    )
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        # Use the enhanced normalize_selector function for consistent handling
        orig_selector = selector
        selector = normalize_selector(selector, logger)
        if selector != orig_selector:
            logger.debug(f"Selector normalized: '{orig_selector}' -> '{selector}'")
        locator = page.locator(selector)
        await locator.wait_for(state=state, timeout=timeout)
        logger.info(f"Waited for {selector} to be {state}")

        action_data = {
            "type": "wait_for_selector",
            "args": {"selector": selector, "state": state, "timeout": timeout},
        }
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after wait_for_selector: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after wait_for_selector: {ActionService.get_instance().actions}"
        )
        await capture_screenshot_for_action(
            page, "wait_for_selector", logger, success=True
        )
        return f"Waited for {selector} to be {state}"
    except Exception as e:
        logger.error(f"Failed to wait for {selector}: {e}")
        return f"Error: Failed to wait for {selector}: {e}"


@tool
async def screenshot(selector: str = None, path: str = None, **kwargs) -> str:
    """Take a screenshot of the current page or a specific element. If selector is None, capture the full page."""
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    dom_service = browser_page.get_dom_service() if browser_page else None
    if selector:
        selector = resolve_selector(selector, dom_service, logger)
        if not selector:
            logger.error("Selector could not be resolved. Aborting screenshot.")
            return "Error: Selector could not be resolved."
    logger.info(
        f"TOOL CALL: screenshot(selector={selector}, path={path}, kwargs={kwargs})"
    )
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()
    try:
        if selector:
            selector = normalize_selector(selector, logger)
            locator = page.locator(selector)
            await locator.screenshot(path=path)
            logger.info(f"Screenshot taken of {selector} at {path}")
        else:
            await page.screenshot(path=path, full_page=True)
            logger.info(f"Full page screenshot taken at {path}")

        action_data = {
            "type": "screenshot",
            "args": {"selector": selector if selector else None, "path": path},
        }
        ActionService.get_instance().record_agent_action(action_data)
        logger.debug(
            f"[browser_tools] Agent actions after screenshot: {ActionService.get_instance().agent_actions}"
        )
        logger.debug(
            f"[browser_tools] Merged actions after screenshot: {ActionService.get_instance().actions}"
        )
        return f"Screenshot taken at {path}"
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return f"Error: Failed to take screenshot: {e}"


# Not an LLM tool. Used internally by DOM service.
async def list_interactive_elements() -> str:
    """List interactive elements on the page. (Internal service, not an LLM tool.)"""
    pass


# --- LLM Tool: List Suggestions for Dropdown/Autocomplete ---


@langchain_tool
@resolve_hash_args
async def list_suggestions(
    container_selector: str, option_selector: str = None, **kwargs
) -> str:
    """
    List all options from a dropdown (<select>) element specified by selector.
    Args:
        selector: CSS or XPath selector for the <select> element.
    Returns:
        JSON list of {label, value, index} for each <option>.
    """
    import json
    import logging

    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return json.dumps({"error": "No active browser page."})
    page = browser_page.get_page()
    dom_service = (
        browser_page.get_dom_service()
        if hasattr(browser_page, "get_dom_service")
        else None
    )

    try:
        # from .browser_tools import resolve_selector  # unused import

        option_selector = option_selector or "> *"
        container_selector = normalize_selector(container_selector, logger)
        option_selector = normalize_selector(option_selector, logger)
        # Handle XPath selectors specially - can't combine XPath selectors with spaces
        if container_selector.startswith("xpath=") or option_selector.startswith(
            "xpath="
        ):
            if container_selector.startswith("xpath=") and option_selector.startswith(
                "xpath="
            ):
                logger.warning(
                    "Cannot combine two XPath selectors, using container_selector only"
                )
                locator = page.locator(container_selector)
            elif container_selector.startswith("xpath="):
                logger.warning(
                    "Using XPath container_selector only, ignoring option_selector"
                )
                locator = page.locator(container_selector)
            else:
                logger.warning(
                    "Using XPath option_selector only, ignoring container_selector"
                )
                locator = page.locator(option_selector)
        else:
            locator = page.locator(f"{container_selector} {option_selector}")
        count = await locator.count()
        logger.info(f"[list_suggestions] Found {count} options in {container_selector}")
        suggestions = []
        for idx in range(count):
            option = locator.nth(idx)
            try:
                label = await option.inner_text()
            except Exception as e:
                logger.warning(
                    f"[list_suggestions] Failed to get label for option {idx}: {e}"
                )
                label = ""
            hash_val = None
            if dom_service:
                try:
                    hash_val = await option.evaluate(
                        "el => el.getAttribute('data-t2b-hash')"
                    )
                except Exception as e:
                    logger.debug(
                        f"[list_suggestions] Could not get hash for option {idx}: {e}"
                    )
            has_link = False
            link_text = None
            link_hash = None
            try:
                link_locator = option.locator("a")
                link_count = await link_locator.count()
                if link_count > 0:
                    has_link = True
                    link = link_locator.nth(0)
                    try:
                        link_text = await link.inner_text()
                    except Exception as e:
                        logger.debug(
                            f"[list_suggestions] Could not get link text for option {idx}: {e}"
                        )
                    if dom_service:
                        try:
                            link_hash = await link.evaluate(
                                "el => el.getAttribute('data-t2b-hash')"
                            )
                        except Exception as e:
                            logger.debug(
                                f"[list_suggestions] Could not get link hash for option {idx}: {e}"
                            )
            except Exception as e:
                logger.debug(f"[list_suggestions] No link found in option {idx}: {e}")
            suggestions.append(
                {
                    "label": label.strip() if label else "",
                    "hash": hash_val,
                    "has_link": has_link,
                    "link_text": link_text,
                    "link_hash": link_hash,
                }
            )
        logger.info(f"[list_suggestions] Suggestions: {suggestions}")
        return json.dumps(suggestions)
    except Exception as e:
        logger.error(f"[list_suggestions] Failed: {e}")
        return json.dumps({"error": str(e)})


# --- LLM Tool: Generate PDF from HTML ---
@tool
def generate_pdf_from_html(html: str, path: str = None, options: dict = None) -> str:
    """
    Generate a high-quality PDF from HTML content using Playwright with enhanced formatting.

    Args:
        html (str): HTML content to convert to PDF
        path (str, optional): Output PDF path. If provided, timestamp will be inserted before .pdf extension
        options (dict, optional): PDF generation options including:
            - page_size: 'A4', 'Letter', 'Legal' (default: 'A4')
            - orientation: 'portrait', 'landscape' (default: 'portrait')
            - margins: dict with top, bottom, left, right in inches (default: 0.75")
            - print_background: bool (default: True)
            - scale: float 0.1-2.0 (default: 1.0)
            - header_template: str HTML template for header
            - footer_template: str HTML template for footer
            - display_header_footer: bool (default: True)
            - quality: 'high', 'medium', 'low' (default: 'high')

    Returns:
        str: Path to the generated PDF or error message
    """
    import logging
    import asyncio
    from pathlib import Path
    from datetime import datetime
    from playwright.async_api import async_playwright
    import os

    logger = logging.getLogger(__name__)
    logger.info("TOOL CALL: generate_pdf_from_html() called with enhanced options")

    # Default options for enhanced PDF quality
    default_options = {
        "page_size": "A4",
        "orientation": "portrait",
        "margins": {
            "top": "0.75in",
            "bottom": "0.75in",
            "left": "0.75in",
            "right": "0.75in",
        },
        "print_background": True,
        "scale": 1.0,
        "display_header_footer": True,
        "header_template": """
        <div style="font-size: 10px; color: #666; width: 100%; text-align: center; margin: 0 20px;">
            <span style="float: left;">Generated by Talk2Browser</span>
            <span style="float: right;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
        </div>
        """,
        "footer_template": """
        <div style="font-size: 9px; color: #888; width: 100%; text-align: center; margin: 0 20px;">
            <span>Generated on: {timestamp}</span>
        </div>
        """.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        "quality": "high",
    }

    # Merge user options with defaults
    if options is None:
        options = {}
    merged_options = {**default_options, **options}

    def enhance_html_styling(html_content: str) -> str:
        """Add enhanced CSS styling to improve PDF appearance"""
        enhanced_css = """
        <style>
            body {
                font-family: 'Inter', 'Segoe UI', 'Roboto', sans-serif;
                line-height: 1.6;
                color: #2d3748;
                margin: 0;
                padding: 20px;
                background: white;
            }
            h1, h2, h3, h4, h5, h6 {
                font-weight: 700;
                margin-top: 2em;
                margin-bottom: 0.5em;
                color: #1a202c;
            }
            h1 { font-size: 2.25rem; border-bottom: 3px solid #4299e1; padding-bottom: 0.5rem; }
            h2 { font-size: 1.875rem; border-bottom: 2px solid #63b3ed; padding-bottom: 0.3rem; }
            h3 { font-size: 1.5rem; color: #2b6cb0; }
            h4 { font-size: 1.25rem; color: #3182ce; }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 1.5em 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-radius: 8px;
                overflow: hidden;
            }
            th {
                background: linear-gradient(135deg, #4299e1, #3182ce);
                color: white;
                font-weight: 600;
                padding: 12px 16px;
                text-align: left;
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            td {
                padding: 12px 16px;
                border-bottom: 1px solid #e2e8f0;
                font-size: 0.95rem;
            }
            tr:nth-child(even) { background-color: #f7fafc; }
            tr:hover { background-color: #edf2f7; }
            pre, code {
                font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
                background: #2d3748;
                color: #e2e8f0;
                border-radius: 6px;
            }
            pre {
                padding: 1rem;
                margin: 1rem 0;
                overflow-x: auto;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            code {
                padding: 0.2em 0.4em;
                font-size: 0.9em;
            }
            ul, ol {
                margin: 1em 0;
                padding-left: 2em;
            }
            li {
                margin: 0.5em 0;
                line-height: 1.6;
            }
            blockquote {
                border-left: 4px solid #4299e1;
                background: #f7fafc;
                margin: 1.5em 0;
                padding: 1em 1.5em;
                font-style: italic;
                border-radius: 0 6px 6px 0;
            }
            a {
                color: #3182ce;
                text-decoration: none;
                border-bottom: 1px solid transparent;
                transition: border-color 0.2s;
            }
            a:hover { border-bottom-color: #3182ce; }
            .section {
                background: white;
                border-radius: 8px;
                padding: 1.5rem;
                margin: 1rem 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                border: 1px solid #e2e8f0;
            }
            .badge {
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .badge-success { background: #c6f6d5; color: #22543d; }
            .badge-warning { background: #faf089; color: #744210; }
            .badge-error { background: #fed7d7; color: #742a2a; }
            .badge-info { background: #bee3f8; color: #2a4365; }
            .page-break { page-break-before: always; }
            @media print {
                body { font-size: 12pt; }
                h1 { font-size: 18pt; }
                h2 { font-size: 16pt; }
                h3 { font-size: 14pt; }
                .no-print { display: none; }
                a { color: #000; text-decoration: none; }
                a[href]:after {
                    content: " (" attr(href) ")";
                    font-size: 10pt;
                    color: #666;
                }
            }
        </style>
        """
        if "<head>" in html_content and "</head>" in html_content:
            html_content = html_content.replace("</head>", f"{enhanced_css}</head>")
        elif "<html>" in html_content:
            html_content = html_content.replace(
                "<html>", f"<html><head>{enhanced_css}</head>"
            )
        else:
            html_content = (
                f"<html><head>{enhanced_css}</head><body>{html_content}</body></html>"
            )
        return html_content

    async def _generate():
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    args=["--disable-web-security", "--allow-running-insecure-content"]
                )
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1200, "height": 800})
                # Convert markdown to HTML if needed
                import markdown

                html_to_use = html
                if "<html" not in html.lower():
                    html_to_use = markdown.markdown(html)
                enhanced_html = enhance_html_styling(html_to_use)
                await page.set_content(enhanced_html, wait_until="networkidle")
                pdf_dir = Path("./generated/pdf")
                pdf_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if path:
                    pth = Path(path)
                    filename = pth.name
                    if filename.lower().endswith(".pdf"):
                        filename = f"{pth.stem}_{timestamp}{pth.suffix}"
                    else:
                        filename = f"{filename}_{timestamp}.pdf"
                    output_path = str(pdf_dir / filename)
                else:
                    output_path = str(pdf_dir / f"enhanced_report_{timestamp}.pdf")
                logger.info(
                    f"[generate_pdf_from_html] Generating enhanced PDF: {output_path}"
                )
                pdf_options = {
                    "path": output_path,
                    "format": merged_options["page_size"],
                    "landscape": merged_options["orientation"] == "landscape",
                    "margin": merged_options["margins"],
                    "print_background": merged_options["print_background"],
                    "scale": merged_options["scale"],
                    "display_header_footer": merged_options["display_header_footer"],
                    "header_template": merged_options["header_template"],
                    "footer_template": merged_options["footer_template"],
                }
                if merged_options["quality"] == "high":
                    pdf_options["prefer_css_page_size"] = True
                elif merged_options["quality"] == "low":
                    pdf_options["scale"] = 0.8
                # Ensure all margin values are strings (Playwright requires this)
                pdf_options["margin"] = {
                    k: str(v) if not isinstance(v, str) else v
                    for k, v in pdf_options["margin"].items()
                }
                logger.info(
                    f"[generate_pdf_from_html] Calling Playwright page.pdf with options: {pdf_options}"
                )
                await page.pdf(**pdf_options)
                logger.info(
                    f"[generate_pdf_from_html] Playwright PDF generated at {output_path}"
                )
                await browser.close()
                # Append screenshots as additional pages

                actions = ActionService.get_instance().actions
                screenshot_paths = [
                    a["args"]["path"]
                    for a in actions
                    if a.get("type") == "screenshot" and "path" in a.get("args", {})
                ]
                if screenshot_paths:
                    try:
                        from PyPDF2 import PdfReader, PdfWriter
                        from fpdf import FPDF
                        from PIL import Image

                        temp_pdf_paths = []
                        writer = PdfWriter()
                        reader = PdfReader(output_path)
                        # Add original PDF pages
                        for page in reader.pages:
                            writer.add_page(page)
                        # Create a PDF for each screenshot and append
                        for idx, img_path in enumerate(screenshot_paths):
                            if not os.path.exists(img_path):
                                continue
                            pdf_img = FPDF(unit="mm", format="A4")
                            pdf_img.add_page()
                            img = Image.open(img_path)
                            img_w, img_h = img.size
                            page_w, page_h = 210, 297
                            margin = 10
                            max_w = page_w - 2 * margin
                            max_h = page_h - 2 * margin
                            scale = min(max_w / img_w, max_h / img_h)
                            display_w = img_w * scale
                            display_h = img_h * scale
                            x = (page_w - display_w) / 2
                            y = (page_h - display_h) / 2
                            pdf_img.image(img_path, x=x, y=y, w=display_w, h=display_h)
                            temp_img_pdf = str(
                                pdf_dir / f"screenshot_{idx}_{timestamp}.pdf"
                            )
                            pdf_img.output(temp_img_pdf)
                            temp_pdf_paths.append(temp_img_pdf)
                        # Append screenshot PDFs
                        for temp_pdf in temp_pdf_paths:
                            img_reader = PdfReader(temp_pdf)
                            for page in img_reader.pages:
                                writer.add_page(page)
                            logger.info(
                                f"[generate_pdf_from_html] Appending screenshot PDF: {temp_pdf}"
                            )
                        with open(output_path, "wb") as f_out:
                            writer.write(f_out)
                        for temp_pdf in temp_pdf_paths:
                            os.remove(temp_pdf)
                            logger.info(
                                f"[generate_pdf_from_html] Deleted temp screenshot PDF: {temp_pdf}"
                            )
                    except Exception as e:
                        logger.error(
                            f"[generate_pdf_from_html] Failed to append screenshots to PDF: {e}"
                        )
                pdf_path = Path(output_path)
                if pdf_path.exists():
                    file_size = pdf_path.stat().st_size
                    logger.info(
                        f"Enhanced PDF generated successfully: {output_path} ({file_size:,} bytes)"
                    )
                else:
                    raise Exception("PDF file was not created")
                action_data = {
                    "type": "generate_pdf_from_html",
                    "args": {
                        "html": "<omitted>",
                        "path": output_path,
                        "options": merged_options,
                        "file_size": file_size,
                        "enhanced": True,
                    },
                }
                ActionService.get_instance().record_agent_action(action_data)
                logger.info(
                    f"[generate_pdf_from_html] Enhanced PDF generation completed with options: {merged_options}"
                )
                logger.info(
                    f"[generate_pdf_from_html] Returning output path: {output_path}"
                )
                return output_path
        except Exception as e:
            logger.error(
                f"[generate_pdf_from_html] PDF generation failed: {e}", exc_info=True
            )
            raise

    # Execute the async function and return the result
    return asyncio.run(_generate())


@tool
async def extract_structured_data(
    extract_links: bool = False, include_hidden: bool = False, **kwargs
):
    """
    Extract the current web page as markdown for structured data extraction by LLMs.
    Optimized for large/slow pages: longer timeouts, partial results on timeout, and diagnostic logging.
    Args:
        extract_links: Whether to preserve links in the extracted content (default: False)
        include_hidden: Whether to include hidden elements in extraction (default: False)
    Returns:
        str: Markdown version of the web page (truncated if too large)
    """
    import time
    import re
    import asyncio

    logger = logging.getLogger(__name__)
    logger.info(
        f"TOOL CALL: extract_structured_data(extract_links={extract_links}, include_hidden={include_hidden})"
    )
    try:
        browser_page = PageManager.get_instance().get_current_page()
        if not browser_page:
            logger.error("No active browser page found in PageManager.")
            return "Error: No active browser page."

        page = browser_page.get_page()
        current_url = page.url
        logger.info(f"[extract_structured_data] Extracting from URL: {current_url}")

        await page.wait_for_load_state("networkidle")
        logger.info("[extract_structured_data] Page load state: networkidle reached")

        try:
            import markdownify

            strip = []
            if not extract_links:
                strip = ["a", "img"]
            logger.info(f"[extract_structured_data] Markdownify strip tags: {strip}")

            loop = asyncio.get_event_loop()
            start_time = time.time()
            # Increase timeout for slow/large pages
            page_html_result = None
            try:
                page_html_result = await asyncio.wait_for(page.content(), timeout=30.0)
                logger.info(
                    f"[extract_structured_data] Raw HTML extracted, length: {len(page_html_result)} characters"
                )
                logger.info(
                    f"[extract_structured_data] HTML preview (first 500 chars): {page_html_result[:500]}"
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Timeout while extracting page HTML content (30s exceeded)"
                )
                return "Error: Timeout while extracting page HTML content (30 seconds exceeded)"
            logger.info(
                f"[extract_structured_data] Page content extraction took {time.time() - start_time:.2f}s"
            )

            page_html = page_html_result

            def markdownify_func(html):
                return markdownify.markdownify(html, strip=strip)

            content = None
            try:
                md_start = time.time()
                content = await asyncio.wait_for(
                    loop.run_in_executor(None, markdownify_func, page_html),
                    timeout=30.0,
                )
                logger.info(
                    f"[extract_structured_data] Markdownify took {time.time() - md_start:.2f}s"
                )
                logger.info(
                    f"[extract_structured_data] Markdown content length: {len(content)} characters"
                )
                logger.info(
                    f"[extract_structured_data] Markdown preview (first 1000 chars): {content[:1000]}"
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout during markdownify conversion (30s exceeded). Returning partial HTML content as fallback."
                )
                # Return partial HTML as fallback, truncated if needed
                fallback_html = (
                    page_html[:15000] + "\n... [TRUNCATED DUE TO TIMEOUT] ...\n"
                    if page_html
                    else ""
                )
                logger.info(
                    f"[extract_structured_data] Returning fallback HTML, length: {len(fallback_html)}"
                )
                return f"Warning: Timeout during markdownify conversion (30s). Partial HTML content returned.\n\n{fallback_html}"
            except Exception as e:
                logger.warning(f"Markdownify failed: {type(e).__name__}: {str(e)}")
                return f"Error: Could not convert html to markdown: {type(e).__name__}: {str(e)}"

            # Iframe extraction (keep timeouts aggressive)
            iframe_count = 0
            for iframe in page.frames:
                try:
                    await asyncio.wait_for(
                        iframe.wait_for_load_state(timeout=1000), timeout=2.0
                    )
                except Exception:
                    pass
                if (
                    iframe.url != page.url
                    and not iframe.url.startswith("data:")
                    and not iframe.url.startswith("about:")
                ):
                    iframe_count += 1
                    content += f"\n\nIFRAME {iframe.url}:\n"
                    try:
                        iframe_html = await asyncio.wait_for(
                            iframe.content(), timeout=5.0
                        )
                        iframe_markdown = await asyncio.wait_for(
                            loop.run_in_executor(None, markdownify_func, iframe_html),
                            timeout=5.0,
                        )
                        logger.info(
                            f"[extract_structured_data] Iframe {iframe_count} content extracted, length: {len(iframe_markdown)}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"[extract_structured_data] Failed to extract iframe {iframe_count}: {str(e)}"
                        )
                        iframe_markdown = ""
                    content += iframe_markdown

            logger.info(
                f"[extract_structured_data] Total iframes processed: {iframe_count}"
            )

            cleaned_content = re.sub(r"\n+", "\n", content)
            logger.info(
                f"[extract_structured_data] After cleaning, content length: {len(cleaned_content)} characters"
            )

            max_chars = 30000
            if len(cleaned_content) > max_chars:
                logger.info(
                    f"Content is too long, removing middle {len(cleaned_content) - max_chars} characters"
                )
                cleaned_content = (
                    cleaned_content[: max_chars // 2]
                    + "\n... left out the middle because it was too long ...\n"
                    + cleaned_content[-max_chars // 2 :]
                )
                logger.info(
                    f"[extract_structured_data] After truncation, content length: {len(cleaned_content)} characters"
                )

            logger.info(
                f"[extract_structured_data] Final content length: {len(cleaned_content)} characters"
            )
            logger.info(
                f"[extract_structured_data] Final content preview (first 2000 chars):\n{cleaned_content[:2000]}"
            )
            logger.info(
                f"[extract_structured_data] Final content preview (last 1000 chars):\n{cleaned_content[-1000:]}"
            )

            ActionService.get_instance().record_action(
                {
                    "type": "extract_structured_data",
                    "args": {
                        "extract_links": extract_links,
                        "include_hidden": include_hidden,
                        "content_length": len(cleaned_content),
                    },
                }
            )

            logger.info(
                f"[extract_structured_data] Successfully returning {len(cleaned_content)} characters of extracted content"
            )
            return cleaned_content
        except ImportError:
            logger.warning("markdownify not available, using plain text extraction")
            # Fallback to plain text extraction
            content = await page.inner_text("body")
            logger.info(
                f"[extract_structured_data] Fallback plain text extraction, length: {len(content)} characters"
            )
            logger.info(
                f"[extract_structured_data] Plain text preview (first 1000 chars): {content[:1000]}"
            )
            return content
    except Exception as e:
        logger.error(f"Error extracting structured data: {str(e)}", exc_info=True)
        return f"Error extracting structured data: {str(e)}"
