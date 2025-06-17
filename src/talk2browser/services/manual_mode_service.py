import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Import ActionService singleton or instance
from .action_service import ActionService
# Singleton instance for now (could be moved to a dedicated singleton file if needed)
action_service = ActionService()

class ManualModeService:
    ...
    async def expose_mode_change_handler(self, page):
        """
        Expose the mode change handler to Playwright JS as notifyPythonOfModeChange.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Exposing notifyPythonOfModeChange to Playwright page.")
        await page.expose_function("notifyPythonOfModeChange", self.handle_mode_change)

    """
    Service to manage manual/agent mode switching, agent pause/resume, and manual mode timeout prompts.
    Optionally interacts with DOMService for browser-side UI.
    """
    def __init__(self, dom_service: Optional[object] = None):
        self._resume_event = asyncio.Event()
        self._resume_event.set()  # Start in agent mode
        self._manual_mode = False
        self.dom_service = dom_service
        self._timeout_task = None

    def handle_mode_change(self, is_manual: bool, page=None, timeout_seconds=120):
        """
        Called by Playwright/JS when the user toggles manual/agent mode.
        Optionally starts a timeout monitor if entering manual mode.
        """
        self._manual_mode = is_manual
        if is_manual:
            logger.info("Manual mode ON: pausing agent.")
            self._resume_event.clear()
            if self.dom_service and page:
                # Start timeout monitor to show popup if needed
                if self._timeout_task is None or self._timeout_task.done():
                    self._timeout_task = asyncio.create_task(
                        self._manual_mode_timeout_monitor(page, timeout_seconds)
                    )
        else:
            logger.info("Agent mode ON: resuming agent.")
            self._resume_event.set()
            # Cancel timeout monitor if running
            if self._timeout_task and not self._timeout_task.done():
                self._timeout_task.cancel()

    async def _manual_mode_timeout_monitor(self, page, timeout_seconds):
        try:
            while self._manual_mode:
                try:
                    await asyncio.wait_for(self._resume_event.wait(), timeout=timeout_seconds)
                    break  # User switched back to agent mode
                except asyncio.TimeoutError:
                    logger.info("Manual mode timeout reached, showing popup.")
                    if self.dom_service:
                        await self.dom_service.show_manual_mode_timeout_popup()
                    await asyncio.sleep(10)  # Wait before next popup
        except asyncio.CancelledError:
            logger.info("Manual mode timeout monitor cancelled.")

    async def wait_if_manual_mode(self):
        if not self._resume_event.is_set():
            logger.info("Agent paused. Waiting for user to finish manual actions...")
            await self._resume_event.wait()

    @property
    def is_manual_mode(self):
        return self._manual_mode

    # Example: Retrieve manual actions from the browser context
    async def get_manual_actions(self, page):
        logger.info("Fetching manual actions from browser...")
        actions = await page.evaluate("window.getManualActions && window.getManualActions()")
        logger.debug(f"Fetched {len(actions) if actions else 0} manual actions from browser. Delegating recording to ActionService.")
        from .action_service import action_service
        for action in actions or []:
            action_service.record_manual_action(action)
        return actions

    async def save_manual_actions(self, page, output_path):
        actions = await self.get_manual_actions(page)
        from .action_service import action_service
        action_service.save_manual_actions(output_path)
        logger.info(f"Manual actions saved to {output_path} via ActionService")
        return output_path
