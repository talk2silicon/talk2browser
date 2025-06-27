import logging
import traceback

async def handle_tool_exception(page, selector, error_msg, logger, screenshot_prefix="error"):
    """
    Handle exceptions in browser tools by logging, capturing a screenshot, and standardizing the error response.

    Args:
        page: The Playwright page object.
        selector: The selector involved in the failed action (if any).
        error_msg: The error message or exception string.
        logger: Logger instance.
        screenshot_prefix: Prefix for the screenshot filename.

    Returns:
        str: Standardized error message for the agent.
    """
    logger.error(f"[Tool Exception] {error_msg}\nSelector: {selector}")
    logger.debug(traceback.format_exc())
    screenshot_path = None
    try:
        from pathlib import Path
        screenshots_dir = Path("./screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = str(screenshots_dir / f"{screenshot_prefix}_{(selector or 'unknown').replace('/', '_').replace(' ', '_')}_{timestamp}.png")
        await page.screenshot(path=screenshot_path)
        logger.info(f"Screenshot saved to {screenshot_path} for exception.")
    except Exception as screenshot_exc:
        logger.warning(f"Failed to capture screenshot: {screenshot_exc}")

    return f"Error: {error_msg} (see {screenshot_path or 'log'} for details)"
