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
        logger.debug(f"Recording agent action: {action}")
        self.agent_actions.append(action)
        logger.debug(f"Agent actions now has {len(self.agent_actions)} actions: {self.agent_actions}")
        logger.debug(f"Merged actions: {self.merged_actions}")

    def __init__(self):
        if ActionService._instance is not None:
            raise RuntimeError("ActionService is a singleton. Use ActionService.get_instance().")
        self.manual_actions: List[Dict[str, Any]] = []
        self.agent_actions: List[Dict[str, Any]] = []
        self.merged_actions: List[Dict[str, Any]] = []
        logger.debug("ActionService singleton instance initialized.")
        ActionService._instance = self

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logger.debug("Creating new ActionService singleton instance.")
            cls._instance = ActionService()
        else:
            logger.debug("Returning existing ActionService singleton instance.")
        return cls._instance

    def record_manual_action(self, action: dict) -> None:
        logger.debug(f"Recording manual action: {action}")
        self.manual_actions.append(action)

    def record_manual_actions(self, actions: List[Dict[str, Any]]) -> None:
        logger.debug(f"Recording batch of {len(actions)} manual actions")
        for action in actions:
            self.record_manual_action(action)

    def record_manual_actions_list(self, actions: List[Dict[str, Any]]):
        logger.info(f"Recording {len(actions)} manual actions.")
        self.manual_actions = actions

    def get_manual_actions(self) -> List[Dict[str, Any]]:
        return self.manual_actions

    def get_agent_actions(self) -> List[Dict[str, Any]]:
        return self.agent_actions

    def set_merged_actions(self, actions: List[Dict[str, Any]]):
        logger.info(f"Setting merged actions ({len(actions)}) from LLM.")
        self.merged_actions = actions

    def get_merged_actions(self) -> List[Dict[str, Any]]:
        return self.merged_actions

    def merge_and_store_actions(self):
        """
        Merge manual and agent actions using the merge_actions utility, store in self.merged_actions, and log.
        Returns the merged list.
        """
        merged = merge_actions(self.manual_actions, self.agent_actions)
        self.merged_actions = merged
        logger.info(f"[ActionService] Merged {len(self.manual_actions)} manual and {len(self.agent_actions)} agent actions into {len(merged)} merged actions.")
        return merged

    def clear(self):
        logger.info("Clearing all recorded actions.")
        self.manual_actions = []
        self.agent_actions = []
        self.merged_actions = []

    def save_action_lists(self, path: str):
        logger.info(f"Saving all action lists to {path} via save_json_to_file")
        from ..tools.file_system_tools import save_json_to_file
        save_json_to_file(path, {
            "manual_actions": self.manual_actions,
            "agent_actions": self.agent_actions,
            "merged_actions": self.merged_actions
        })

    def load_action_lists(self, path: str):
        logger.info(f"Loading action lists from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.manual_actions = data.get("manual_actions", [])
        self.agent_actions = data.get("agent_actions", [])
        self.merged_actions = data.get("merged_actions", [])
        return data

    def load_merged_actions(self, path: str) -> List[Dict[str, Any]]:
        logger.info(f"Loading merged actions from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("merged_actions", [])
