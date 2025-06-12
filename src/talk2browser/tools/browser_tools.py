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
        element_map = kwargs.get("element_map", {})
        if "selector" in kwargs and isinstance(kwargs["selector"], str) and kwargs["selector"].startswith("#"):
            hash_val = kwargs["selector"]
            logger = logging.getLogger(__name__)
            logger.debug(f"Attempting to resolve hash selector: {hash_val}")
            resolved = element_map.get(hash_val)
            if resolved:
                logger.info(f"Resolved hash {hash_val} to selector: {resolved}")
                kwargs["selector"] = resolved
            else:
                logger.warning(f"Hash {hash_val} not found in element_map! element_map keys: {list(element_map.keys())}")
        else:
            logger = logging.getLogger(__name__)
            logger.debug(f"Selector '{kwargs.get('selector')}' is not a hash or not present; skipping hash resolution.")
        return await tool_func(*args, **kwargs)
    wrapper._is_browser_tool = True
    return wrapper

# Global page reference
_page: Optional[Page] = None

@tool
@resolve_hash_args
async def get_all_elements(selector: str, attribute: str = "", **kwargs) -> str:
    """Get a list of text or attribute values for all elements matching the selector.
    Args:
        selector: CSS selector
        attribute: If provided, returns this attribute for each element; otherwise, returns text content.
    Returns:
        str: JSON list of values
    """
    import logging
    import json
    logger = logging.getLogger(__name__)
    if not _page:
        error_msg = "Page not set. Call set_page() first"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    try:
        elements = await _page.query_selector_all(selector)
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
    """Check if an element is enabled (not disabled).
    Args:
        selector: CSS selector
    Returns:
        bool: True if enabled, False if disabled or not found
    """
    import logging
    logger = logging.getLogger(__name__)
    if not _page:
        logger.error("Page not set. Call set_page() first")
        return False
    try:
        el = await _page.query_selector(selector)
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
    """Return the number of elements matching the selector.
    Args:
        selector: CSS selector
    Returns:
        int: Number of elements found
    """
    import logging
    logger = logging.getLogger(__name__)
    if not _page:
        logger.error("Page not set. Call set_page() first")
        return 0
    try:
        elements = await _page.query_selector_all(selector)
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
    # Record action
    recorder.record_action(
        tool="navigate",
        args={"url": url},
        command=f"await page.goto('{url}')"
    )
    return f"Navigated to {url}. Page title: {title}"

@tool
@resolve_hash_args
async def click(selector: str, timeout: int = 10000, force: bool = False, **kwargs) -> str:
    """Click on an element matching the CSS selector.
    
    Args:
        selector: CSS selector of the element to click
        timeout: Maximum time to wait for the element to be clickable (ms)
        force: If True, use force click (useful for elements that might be obscured)
        
    Returns:
        str: Confirmation message with the clicked element or error details
    """
    import logging
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    logger = logging.getLogger(__name__)
    
    if not _page:
        error_msg = "Page not set. Call set_page() first"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    
    try:
        logger.info(f"Attempting to click element: {selector}")

        # --- Hash resolution: auto-resolve hashes to selectors using DOMService ---
        if selector and isinstance(selector, str) and selector.startswith("#") and len(selector) == 33:
            try:
                from ..browser.dom.service import DOMService
                if _page:
                    dom_service = DOMService(_page)
                    # Ensure element map is up to date
                    await dom_service.get_interactive_elements(highlight=False)
                    element_map = dom_service.get_element_map()
                    resolved = element_map.get(selector)
                    if resolved:
                        logger.info(f"Resolved hash {selector} to selector: {resolved}")
                        selector = resolved
                    else:
                        logger.error(f"Selector '{selector}' looks like a hash but could not be resolved to a real selector via DOMService.")
                        return f"Error: Selector '{selector}' looks like a hash, but could not be resolved to a real selector."
                else:
                    logger.error("_page is not set; cannot resolve hash selector.")
                    return f"Error: _page is not set; cannot resolve hash selector {selector}."
            except Exception as hash_exc:
                logger.error(f"Exception while resolving hash selector: {hash_exc}")
                return f"Error: Exception while resolving hash selector {selector}: {hash_exc}"
        # --- END HASH RESOLUTION ---

        # --- DEBUG: Print all interactive elements with hash and values ---
        try:
            from ..browser.dom.service import DOMService
            if _page:
                dom_service = DOMService(_page)
                elements = await dom_service.get_interactive_elements(highlight=False)
                logger.info("Interactive elements on page (hash, tag, text, attributes):")
                for el in elements:
                    logger.info(f"  hash=#{el.element_hash} tag={el.tag_name} text={el.text} attrs={el.attributes}")
            else:
                logger.warning("_page is not set; cannot print interactive elements.")
        except Exception as debug_elem_exc:
            logger.error(f"Failed to print interactive elements for debug: {debug_elem_exc}")
        # --- END DEBUG ---

        # Wait for the element to be visible and enabled
        element = await _page.wait_for_selector(
            selector,
            state="visible",
            timeout=timeout
        )
        
        # Scroll the element into view
        await element.scroll_into_view_if_needed()
        
        # Check if element is enabled
        is_disabled = await element.evaluate('el => el.disabled')
        if is_disabled:
            error_msg = f"Element {selector} is disabled"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        # Wait for the element to be in the viewport and clickable
        try:
            await _page.wait_for_selector(
                f"{selector}:not([disabled]):not([aria-disabled='true'])",
                state="visible",
                timeout=5000
            )
        except PlaywrightTimeoutError:
            logger.warning(f"Element {selector} may not be clickable, but trying anyway")
        
        # Try different click methods in sequence
        click_methods = [
            ("standard", lambda: element.click()),
            ("force_click", lambda: element.click(force=True, timeout=5000)),
            ("javascript_click", lambda: element.evaluate('el => el.click()'))
        ]
        
        last_error = None
        for method_name, click_func in click_methods:
            try:
                logger.debug(f"Trying {method_name} click on {selector}")
                await click_func()
                logger.info(f"Successfully clicked element using {method_name}: {selector}")
                # Record action
                recorder.record_action(
                    tool="click",
                    args={"selector": selector, "timeout": timeout, "force": force},
                    command=f"await page.click('{selector}', timeout={timeout}, force={force})"
                )
                return f"Clicked element: {selector} (method: {method_name})"
            except Exception as e:
                last_error = e
                logger.warning(f"{method_name} click failed: {str(e)}")
                continue
        
        # If all methods failed, try a final time with force if not already tried
        if not force:
            try:
                logger.debug(f"Trying final force click on {selector}")
                await element.click(force=True, timeout=5000)
                logger.info(f"Successfully force-clicked element: {selector}")
                # Record action
                recorder.record_action(
                    tool="click",
                    args={"selector": selector, "timeout": timeout, "force": force},
                    command=f"await page.click('{selector}', timeout={timeout}, force={force})"
                )
                return f"Clicked element: {selector} (method: final_force_click)"
            except Exception as e:
                last_error = e
                logger.error(f"Final force click also failed: {str(e)}")
        
        # If we get here, all click attempts failed
        error_msg = f"All click attempts failed for {selector}: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to click element {selector}: {str(e)}"
        logger.error(error_msg)
        
        # Take a screenshot to help with debugging
        try:
            screenshot = await _page.screenshot(
                type='png',
                full_page=True,
                path=f"click_error_{selector.replace(' ', '_').replace('.', '_')}.png"
            )
            logger.debug(f"Screenshot saved to click_error_{selector}.png")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
            
        # Get page HTML for debugging
        try:
            html = await _page.content()
            with open(f"click_error_{selector}.html", "w") as f:
                f.write(html)
            logger.debug(f"Page HTML saved to click_error_{selector}.html")
        except Exception as html_error:
            logger.error(f"Failed to save page HTML: {html_error}")
            
        return f"Error: {error_msg}"

@tool
@resolve_hash_args
async def fill(selector: str, text: str, **kwargs) -> str:
    """Fill a form field with the specified text.
    
    Args:
        selector: CSS selector of the input field
        text: Text to fill in the field
        
    Returns:
        str: Confirmation message or error details
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not _page:
        error_msg = "Page not set. Call set_page() first"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    
    try:
        logger.info(f"Attempting to fill field {selector} with text: {text}")
        
        # Wait for the element to be visible and enabled
        element = await _page.wait_for_selector(
            selector,
            state="visible",
            timeout=10000  # 10 second timeout
        )
        
        # Scroll the element into view
        await element.scroll_into_view_if_needed()
        
        # Clear the field first
        await element.fill("")
        
        # Type the text with a small delay between keystrokes
        await _page.fill(selector, text)
        # Record action
        recorder.record_action(
            tool="fill",
            args={"selector": selector, "text": text},
            command=f"await page.fill('{selector}', '{text}')"
        )
        
        # Verify the text was entered
        value = await element.input_value()
        if value != text:
            error_msg = f"Failed to verify text in {selector}. Expected: '{text}', Got: '{value}'"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        logger.info(f"Successfully filled field {selector}")
        return f"Filled '{text}' into {selector}"
        
    except Exception as e:
        error_msg = f"Failed to fill field {selector}: {str(e)}"
        logger.error(error_msg)
        
        # Take a screenshot to help with debugging
        try:
            import os
            os.makedirs('./screenshots', exist_ok=True)
            screenshot_path = f"./screenshots/click_error_{selector}.png"
            screenshot = await _page.screenshot(path=screenshot_path, type='png')
            logger.debug(f"Screenshot taken after error and saved to {screenshot_path} (size: {len(screenshot)} bytes)")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
            
        return f"Error: {error_msg}"

@tool
@resolve_hash_args
async def press(selector: str, key: str, **kwargs) -> str:
    """Press a specific key in an element.
    
    Args:
        selector: CSS selector of the element
        key: Key to press (e.g., 'Enter', 'Tab')
        
    Returns:
        str: Confirmation message
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    await _page.press(selector, key)
    # Record action
    recorder.record_action(
        tool="press",
        args={"selector": selector, "key": key},
        command=f"await page.press('{selector}', '{key}')"
    )
    return f"Pressed '{key}' in {selector}"

@tool
@resolve_hash_args
async def select_option(selector: str, value: str, **kwargs) -> str:
    """Select an option from a dropdown/select element.
    
    Args:
        selector: CSS selector of the select element
        value: Value of the option to select
        
    Returns:
        str: Confirmation message
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    await _page.select_option(selector, value=value)
    # Record action
    recorder.record_action(
        tool="select_option",
        args={"selector": selector, "value": value},
        command=f"await page.select_option('{selector}', '{value}')"
    )
    return f"Selected option '{value}' in {selector}"

@tool
@resolve_hash_args
async def hover(selector: str, **kwargs) -> str:
    """Hover over an element.
    
    Args:
        selector: CSS selector of the element to hover over
        
    Returns:
        str: Confirmation message
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    await _page.hover(selector)
    # Record action
    recorder.record_action(
        tool="hover",
        args={"selector": selector},
        command=f"await page.hover('{selector}')"
    )
    return f"Hovered over {selector}"

@tool
async def screenshot(full_page: bool = False) -> str:
    """Take a screenshot of the current page.
    
    Args:
        full_page: Whether to capture the full scrollable page
        
    Returns:
        str: Base64-encoded screenshot
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    screenshot_bytes = await _page.screenshot(full_page=full_page, type='png')
    return f"data:image/png;base64,{base64.b64encode(screenshot_bytes).decode()}"

@tool
async def evaluate(script: str) -> str:
    """Execute JavaScript in the page context.
    
    Args:
        script: JavaScript code to execute
        
    Returns:
        str: Result of the script execution
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    result = await _page.evaluate(script)
    return str(result)

@tool
@resolve_hash_args
async def wait_for_selector(selector: str, timeout: int = 30000, **kwargs) -> str:
    """Wait for an element to be visible.
    
    Args:
        selector: CSS selector of the element to wait for
        timeout: Maximum time to wait in milliseconds (default: 30000)
        
    Returns:
        str: Confirmation message or error
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not _page:
        error_msg = "Page not set. Call set_page() first"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    
    try:
        logger.info(f"Waiting for selector: {selector} (timeout: {timeout}ms)")
        await _page.wait_for_selector(
            selector, 
            state="visible",
            timeout=timeout
        )
        # Record action
        recorder.record_action(
            tool="wait_for_selector",
            args={"selector": selector, "timeout": timeout},
            command=f"await page.wait_for_selector('{selector}', state='visible', timeout={timeout})"
        )
        logger.info(f"Successfully found visible element: {selector}")
        return f"Element {selector} is now visible"
    except Exception as e:
        error_msg = f"Failed to find element {selector}: {str(e)}"
        logger.error(error_msg)
        # Take a screenshot to help with debugging
        try:
            import os
            os.makedirs('./screenshots', exist_ok=True)
            screenshot_path = f"./screenshots/click_error_{selector}.png"
            screenshot = await _page.screenshot(path=screenshot_path, type='png')
            logger.debug(f"Screenshot taken after error and saved to {screenshot_path} (size: {len(screenshot)} bytes)")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
        
        return f"Error: {error_msg}"

@tool
@resolve_hash_args
async def get_text(selector: str, **kwargs) -> str:
    """Get the text content of an element.
    
    Args:
        selector: CSS selector of the element
        
    Returns:
        str: Text content of the element
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    text = await _page.text_content(selector)
    # Record action
    recorder.record_action(
        tool="get_text",
        args={"selector": selector},
        command=f"await page.text_content('{selector}')"
    )
    return text or ""

@tool
@resolve_hash_args
async def get_attribute(selector: str, attribute: str, **kwargs) -> str:
    """Get an attribute value of an element.
    
    Args:
        selector: CSS selector of the element
        attribute: Name of the attribute to get
        
    Returns:
        str: Value of the attribute
    """
    if not _page:
        raise RuntimeError("Page not set. Call set_page() first")
        
    value = await _page.get_attribute(selector, attribute) or ""
    # Record action
    recorder.record_action(
        tool="get_attribute",
        args={"selector": selector, "attribute": attribute},
        command=f"await page.get_attribute('{selector}', '{attribute}')"
    )
    return value

@tool
@resolve_hash_args
async def is_visible(selector: str, **kwargs) -> bool:
    """Check if an element is visible.
    
    Args:
        selector: CSS selector of the element
        
    Returns:
        bool: True if the element is visible, False otherwise
    """
    if not _page:
        return False
        
    result = await _page.is_visible(selector)
    # Record action
    recorder.record_action(
        tool="is_visible",
        args={"selector": selector},
        command=f"await page.is_visible('{selector}')"
    )
    return result

@tool
async def list_interactive_elements() -> str:
    """List all interactive elements on the current page.
    
    Returns:
        str: Formatted string containing interactive elements and their details
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not _page:
        error_msg = "Page not set. Call set_page() first"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    
    try:
        logger.info("Scanning page for interactive elements...")
        
        # Common interactive elements
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
                count = await _page.locator(selector).count()
                if count > 0:
                    elements.append(f"{selector} ({count} found)")
                    
                    # Get details of the first few elements of each type
                    for i in range(min(3, count)):
                        try:
                            el = _page.locator(selector).nth(i)
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
            screenshot = await _page.screenshot(path=screenshot_path, type='png')
            logger.debug(f"Page screenshot taken and saved to {screenshot_path} (size: {len(screenshot)} bytes)")
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
        
        return "\n".join(result)
        
    except Exception as e:
        error_msg = f"Failed to list interactive elements: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"
