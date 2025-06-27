import json
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ActionService:
    """
    Central service for managing manual, agent, and merged actions.
    Handles in-memory recording and unified save/load for debugging and replay.
    Implements singleton pattern for global access.
    """
    _instance = None

    def record_agent_action(self, action: dict) -> None:
        logger.info(f"[ActionService] Recording agent action: {action}")
        action_type = action.get('type', '')
        args = action.get('args', {})
        element_actions = {'click', 'fill', 'type', 'check', 'uncheck', 'select_option', 'hover'}
        # --- Hash resolution for element-based actions (for merging only, not for saving) ---
        if action_type in element_actions and 'hash' not in args:
            selector = args.get('selector')
            xpath = args.get('xpath')
            hash_val = None
            if self.dom_service:
                try:
                    if selector and isinstance(selector, str) and selector.startswith('#'):
                        hash_val = selector
                    elif xpath and hasattr(self.dom_service, '_element_map'):
                        for h, xp in self.dom_service._element_map.items():
                            if xp == xpath:
                                hash_val = h
                                break
                    if not hash_val:
                        lookup_xpath = selector if selector and (selector.startswith('/') or selector.startswith('html/')) else xpath
                        if lookup_xpath and hasattr(self.dom_service, '_interactive_elements'):
                            for elem in self.dom_service._interactive_elements:
                                if elem.xpath == lookup_xpath:
                                    hash_val = f"#{elem.element_hash}"
                                    break
                    # Only use hash for merging, do NOT add to action JSON
                    if hash_val:
                        logger.info(f"[ActionService] Resolved hash for action: {action_type} -> {hash_val}")
                    else:
                        logger.warning(f"[ActionService] Could not resolve hash for action: {action_type} (selector={selector}, xpath={xpath})")
                except Exception as e:
                    logger.error(f"[ActionService] Exception while resolving hash: {e}")
            else:
                logger.warning("[ActionService] dom_service not set, cannot resolve hash for agent action.")
        # --- Sensitive Data Masking for fill/type ---
        from ..services.sensitive_data_service import SensitiveDataService
        if action_type in {'fill', 'type'}:
            for key in ['text', 'value']:
                if key in args:
                    real_value = args[key]
                    placeholder = None
                    if hasattr(SensitiveDataService, 'get_placeholder_for_value'):
                        placeholder = SensitiveDataService.get_placeholder_for_value(real_value)
                    if placeholder:
                        logger.info(f"[ActionService] Masking sensitive value for {action_type}: {key}={real_value} -> {placeholder}")
                        args[key] = placeholder
        # Remove hash from args before saving JSON
        if 'hash' in args:
            logger.debug(f"[ActionService] Removing hash from action args before saving: {args['hash']}")
            args.pop('hash')
        action['args'] = args
        self.agent_actions.append(action)
        logger.info(f"[ActionService] Agent actions now has {len(self.agent_actions)} actions: {self.agent_actions}")
        self._perform_realtime_merge()

    def __init__(self, dom_service=None):
        if ActionService._instance is not None:
            raise RuntimeError("ActionService is a singleton. Use ActionService.get_instance().")
        self.manual_actions: List[Dict[str, Any]] = []
        self.agent_actions: List[Dict[str, Any]] = []
        self._actions: List[Dict[str, Any]] = []  # Canonical merged list
        self.dom_service = dom_service
        logger.debug("ActionService singleton instance initialized.")
        ActionService._instance = self

        # Manual mode (pause/resume) state
        import asyncio
        self._resume_event = asyncio.Event()
        self._resume_event.set()  # Start in agent mode
        self._manual_mode = False
        self._timeout_task = None

    async def expose_mode_change_handler(self, page):
        """
        Expose the mode change handler to Playwright JS as notifyPythonOfModeChange.
        """
        logger.info("Exposing notifyPythonOfModeChange to Playwright page (via ActionService).")
        await page.expose_function("notifyPythonOfModeChange", self.handle_mode_change)

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
                import asyncio
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
                    import asyncio
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

    async def get_manual_actions(self, page):
        logger.info("Fetching manual actions from browser...")
        actions = await page.evaluate("window.getManualActions && window.getManualActions()")
        logger.debug(f"Fetched {len(actions) if actions else 0} manual actions from browser. Recording with ActionService.")
        # Ensure each action gets a canonical hash via dom_service
        if self.dom_service:
            for action in actions or []:
                # Use selector/xpath from action to get hash
                if 'hash' not in action.get('args', {}):
                    xpath = action.get('args', {}).get('xpath')
                    if xpath:
                        element = self.dom_service.find_element_by_xpath(xpath)
                        if element:
                            action['args']['hash'] = element.element_hash
                self.record_manual_action(action)
        else:
            for action in actions or []:
                self.record_manual_action(action)
        return actions

    async def save_manual_actions(self, page, output_path):
        actions = await self.get_manual_actions(page)
        self.save_action_lists(output_path)
        logger.info(f"Manual actions saved to {output_path} via ActionService")
        return output_path

    def _compute_action_key(self, action: Dict[str, Any]) -> str | None:
        args = action.get('args', {})
        # Prefer hash if present
        if 'hash' in args:
            return args['hash']
        # For non-element actions (like navigate), return None (skip element map checks)
        non_element_actions = {'navigate', 'wait_for_timeout', 'screenshot', 'generate_pdf_from_html'}
        if action.get('type', '') in non_element_actions:
            return None
        # If no hash for element action, fallback to type:selector for debugging only
        selector = args.get('selector', '')
        if selector:
            return f"{action.get('type', '')}:{selector}"
        return None

    def _perform_realtime_merge(self):
        if not self.dom_service:
            logger.warning("DOMService reference not set in ActionService. Merging without DOM context.")
        # Use the DOMService element map if available
        element_map = self.dom_service.get_element_map() if self.dom_service else None
        manual_map = {self._compute_action_key(a): a for a in self.manual_actions if self._compute_action_key(a)}
        merged = []
        used_manual_keys = set()
        for agent_action in self.agent_actions:
            key = self._compute_action_key(agent_action)
            # Only check element map if key is a hash (not None)
            if key and element_map and isinstance(key, str) and key.startswith('#'):
                if key not in element_map:
                    logger.warning(f"Agent action key {key} not found in DOMService element map.\nAction: {agent_action}\nElement map keys: {list(element_map.keys())[:10]} ...")
            if key in manual_map:
                merged.append(manual_map[key])
                used_manual_keys.add(key)
            else:
                merged.append(agent_action)
        for key, manual_action in manual_map.items():
            if key not in used_manual_keys:
                if key and element_map and isinstance(key, str) and key.startswith('#'):
                    if key not in element_map:
                        logger.warning(f"Manual action key {key} not found in DOMService element map.\nAction: {manual_action}\nElement map keys: {list(element_map.keys())[:10]} ...")
                merged.append(manual_action)
        self._actions = merged
        logger.info(f"[ActionService] Real-time merged actions: {self._actions}")

    @classmethod
    def get_instance(cls, dom_service=None):
        if cls._instance is None:
            logger.debug("Creating new ActionService singleton instance.")
            cls._instance = ActionService(dom_service=dom_service)
        else:
            logger.debug("Returning existing ActionService singleton instance.")
            # Optionally update dom_service if provided
            if dom_service is not None:
                cls._instance.set_dom_service(dom_service)
        return cls._instance

    def set_dom_service(self, dom_service):
        logger.info("Setting DOMService reference in ActionService.")
        self.dom_service = dom_service

    def record_manual_action(self, action: dict) -> None:
        import traceback
        logger.info(f"[ActionService] Recording manual action: {action}")
        logger.debug(f"[ActionService] Manual action callstack:\n{traceback.format_stack()}")
        if not self.is_manual_mode:
            logger.warning("[ActionService] Manual action recorded while NOT in manual mode! This may indicate a bug.")
        self.manual_actions.append(action)
        logger.info(f"[ActionService] Manual actions now has {len(self.manual_actions)} actions: {self.manual_actions}")
        self._perform_realtime_merge()

    def record_manual_actions(self, actions: List[Dict[str, Any]]) -> None:
        logger.debug(f"Recording batch of {len(actions)} manual actions")
        self.manual_actions = actions
        self._perform_realtime_merge()

    def record_manual_actions_list(self, actions: List[Dict[str, Any]]):
        logger.info(f"Recording {len(actions)} manual actions.")
        self.manual_actions = actions
        self._perform_realtime_merge()

    def get_manual_actions(self) -> List[Dict[str, Any]]:
        return self.manual_actions

    def pop_new_manual_actions(self) -> List[Dict[str, Any]]:
        """Return and clear all currently recorded manual actions (for one-time injection into agent state)."""
        logger.info(f"[ActionService] Popping {len(self.manual_actions)} new manual actions for agent context injection.")
        actions = self.manual_actions.copy()
        self.manual_actions.clear()
        logger.info("[ActionService] Cleared manual_actions after pop.")
        self._perform_realtime_merge()
        return actions

    def get_agent_actions(self) -> List[Dict[str, Any]]:
        return self.agent_actions

    # REMOVED: set_merged_actions (LLM merge is deprecated)

    @property
    def actions(self) -> List[Dict[str, Any]]:
        return self._actions

    # REMOVED: merge_and_store_actions (merging is now real-time and internal)

    def clear(self):
        logger.info("Clearing all recorded actions.")
        self.manual_actions = []
        self.agent_actions = []
        self._actions = []

    def save_action_lists(self, path: str):
        logger.info(f"Saving all action lists to {path} via save_json_to_file")
        from ..tools.file_system_tools import save_json_to_file
        save_json_to_file(path, {
            "manual_actions": self.manual_actions,
            "agent_actions": self.agent_actions,
            "actions": self._actions
        })

    def save_merged_actions_with_prompt(self, task: str, output_dir: str = "./generated/actions") -> str:
        """
        Save merged actions to a descriptive filename based on the task and timestamp.
        Returns the full path to the saved file.
        """
        import os
        import re
        from datetime import datetime
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "_".join(re.sub(r'[^a-zA-Z0-9]+', ' ', task).lower().split()[:5]) if task else "scenario"
        filename = f"actions_{prefix}_{timestamp}.json"
        path = os.path.join(output_dir, filename)
        from ..tools.file_system_tools import save_json_to_file
        save_json_to_file(path, self._actions)
        logger.info(f"[ActionService] Merged actions saved to {path}")
        return path


    def load_action_lists(self, path: str):
        logger.info(f"Loading action lists from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.manual_actions = data.get("manual_actions", [])
        self.agent_actions = data.get("agent_actions", [])
        self._actions = data.get("actions", [])
        return data

    # REMOVED: load_merged_actions (use load_action_lists and access .actions property)

