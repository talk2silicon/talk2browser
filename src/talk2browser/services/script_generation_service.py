import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ScriptGenerationService:
    """
    Service for generating Playwright, Cypress, and Selenium scripts from action lists.
    Encapsulates LLM prompt construction and output file management.
    """
    def __init__(self, llm=None):
        self.llm = llm  # Optionally inject LLM instance
        self.logger = logger

    async def generate_playwright_script(self, actions: List[Dict[str, Any]], task: str, output_path: Optional[str] = None) -> str:
        """
        Generate a Playwright script from the provided actions using an LLM.
        Args:
            actions: List of action dicts (should be actions from ActionService)
            task: Scenario/task description
            output_path: Optional path to save the script file
        Returns:
            Path to the generated script file
        """
        if not actions:
            self.logger.error("No actions provided for Playwright script generation.")
            raise ValueError("No actions provided.")
        if self.llm is None:
            from ..agent.llm_singleton import get_llm
            self.llm = get_llm()
        formatted_actions = []
        for i, action in enumerate(actions, 1):
            action_type = action.get('type')
            args = action.get('args', {})
            if action_type == 'navigate':
                formatted_actions.append(f"{i}. navigate to {args.get('url', '<missing url>')}")
            elif action_type == 'click':
                formatted_actions.append(f"{i}. click {args.get('selector', '<missing selector>')}")
            elif action_type == 'fill':
                formatted_actions.append(f"{i}. fill {args.get('selector', '<missing selector>')} with {args.get('text', '<missing value>')}")
            else:
                formatted_actions.append(f"{i}. {action_type} {args}")
        prompt = (
            "You are an expert at writing Playwright scripts.\n"
            f"Task: {task}\n"
            f"Actions:\n" + "\n".join(formatted_actions) + "\n"
            "If any action argument is a string like \"${SAUCE_USER}\", generate code that loads the value from the environment variable SAUCE_USER. For example, use os.environ[\"SAUCE_USER\"] in the fill command.\n"
            "Always launch the browser with headless=False for visibility.\n"
            "After each action, add a noticeable pause using time.sleep(1) (remember to import time at the top).\n"
            "Write a valid Playwright Python script for this scenario. Only output the code, no markdown or explanation."
        )
        self.logger.info(f"[ScriptGen] Calling LLM to generate Playwright script for: {task}")
        self.logger.debug(f"[ScriptGen] LLM prompt: {prompt}")
        try:
            response = await self.llm.ainvoke(prompt)
            script = response if isinstance(response, str) else getattr(response, 'content', None) or getattr(response, 'text', None)
            # --- Cleanup unwanted characters: remove markdown code blocks, trim whitespace ---
            if script:
                import re
                script = re.sub(r'^```[a-zA-Z]*', '', script.strip())  # Remove opening code block
                script = re.sub(r'```$', '', script.strip())         # Remove closing code block
                script = script.strip()
            if not script:
                self.logger.error("[ScriptGen] LLM returned no script content.")
                raise ValueError("LLM returned no script content.")
            if output_path is None:
                safe_task = task.lower().replace(' ', '_').replace('/', '_')[:40]
                output_path = str(Path("./generated") / f"playwright_{safe_task}.py")
            from ..tools.file_system_tools import save_text_to_file
            self.logger.debug(f"Saving Playwright script to {output_path}")
            save_text_to_file(output_path, script)
            self.logger.info(f"Playwright script generated at {output_path} via save_text_to_file")
            return str(Path(output_path).absolute())
        except Exception as e:
            self.logger.error(f"Failed to generate Playwright script: {e}")
            raise

    async def generate_cypress_script(self, actions: List[Dict[str, Any]], task: str, output_path: Optional[str] = None) -> str:
        """
        Generate a Cypress script from the provided actions using an LLM.
        Args:
            actions: List of action dicts (should be actions from ActionService)
            task: Scenario/task description
            output_path: Optional path to save the script file
        Returns:
            Path to the generated script file
        """
        if not actions:
            self.logger.error("No actions provided for Cypress script generation.")
            raise ValueError("No actions provided.")
        if self.llm is None:
            from ..agent.llm_singleton import get_llm
            self.llm = get_llm()
        formatted_actions = []
        for i, action in enumerate(actions, 1):
            action_type = action.get('type')
            args = action.get('args', {})
            if action_type == 'navigate':
                formatted_actions.append(f"{i}. navigate to {args.get('url', '<missing url>')}")
            elif action_type == 'click':
                formatted_actions.append(f"{i}. click {args.get('selector', '<missing selector>')}")
            elif action_type == 'fill':
                formatted_actions.append(f"{i}. fill {args.get('selector', '<missing selector>')} with {args.get('text', '<missing value>')}")
            else:
                formatted_actions.append(f"{i}. {action_type} {args}")
        prompt = (
            "You are an expert at writing Cypress scripts.\n"
            f"Task: {task}\n"
            f"Actions:\n" + "\n".join(formatted_actions) + "\n"
            "If any action argument is a string like \"${SAUCE_USER}\", generate code that loads the value from the environment variable SAUCE_USER. For example, use Cypress.env(\"SAUCE_USER\") in the fill command.\n"
            "Write a valid Cypress script for this scenario. Only output the code, no markdown or explanation."
        )
        self.logger.info(f"[ScriptGen] Calling LLM to generate Cypress script for: {task}")
        self.logger.debug(f"[ScriptGen] LLM prompt: {prompt}")
        try:
            response = await self.llm.ainvoke(prompt)
            script = response if isinstance(response, str) else getattr(response, 'content', None) or getattr(response, 'text', None)
            # --- Cleanup unwanted characters: remove markdown code blocks, trim whitespace ---
            if script:
                import re
                script = re.sub(r'^```[a-zA-Z]*', '', script.strip())
                script = re.sub(r'```$', '', script.strip())
                script = script.strip()
            if not script:
                self.logger.error("[ScriptGen] LLM returned no script content.")
                raise ValueError("LLM returned no script content.")
            if output_path is None:
                safe_task = task.lower().replace(' ', '_').replace('/', '_')[:40]
                output_path = str(Path("./generated") / f"cypress_{safe_task}.cy.js")
            from ..tools.file_system_tools import save_text_to_file
            save_text_to_file(output_path, script)
            self.logger.info(f"Cypress script generated at {output_path} via save_text_to_file")
            return str(Path(output_path).absolute())
        except Exception as e:
            self.logger.error(f"Failed to generate Cypress script: {e}")
            raise
    async def generate_selenium_script(self, actions: List[Dict[str, Any]], task: str, output_path: Optional[str] = None) -> str:
        """
        Generate a Selenium script from the provided actions using an LLM.
        Args:
            actions: List of action dicts (should be actions from ActionService)
            task: Scenario/task description
            output_path: Optional path to save the script file
        Returns:
            Path to the generated script file
        """
        if not actions:
            self.logger.error("No actions provided for Selenium script generation.")
            raise ValueError("No actions provided.")
        if self.llm is None:
            from ..agent.llm_singleton import get_llm
            self.llm = get_llm()
        formatted_actions = []
        for i, action in enumerate(actions, 1):
            action_type = action.get('type')
            args = action.get('args', {})
            if action_type == 'navigate':
                formatted_actions.append(f"{i}. navigate to {args.get('url', '<missing url>')}")
            elif action_type == 'click':
                formatted_actions.append(f"{i}. click {args.get('selector', '<missing selector>')}")
            elif action_type == 'fill':
                formatted_actions.append(f"{i}. fill {args.get('selector', '<missing selector>')} with {args.get('text', '<missing value>')}")
            else:
                formatted_actions.append(f"{i}. {action_type} {args}")
        prompt = (
            "You are an expert at writing Selenium test scripts in Python.\n"
            f"Task: {task}\n"
            f"Actions:\n" + "\n".join(formatted_actions) + "\n"
            "If any action argument is a string like \"${SAUCE_USER}\", generate code that loads the value from the environment variable SAUCE_USER. For example, use os.environ[\"SAUCE_USER\"] in the fill command.\n"
            "Write a valid Selenium Python script for this scenario. Only output the code, no markdown or explanation."
        )
        self.logger.info(f"[ScriptGen] Calling LLM to generate Selenium script for: {task}")
        self.logger.debug(f"[ScriptGen] LLM prompt: {prompt}")
        try:
            response = await self.llm.ainvoke(prompt)
            script = response if isinstance(response, str) else getattr(response, 'content', None) or getattr(response, 'text', None)
            # --- Cleanup unwanted characters: remove markdown code blocks, trim whitespace ---
            if script:
                import re
                script = re.sub(r'^```[a-zA-Z]*', '', script.strip())
                script = re.sub(r'```$', '', script.strip())
                script = script.strip()
            if not script:
                self.logger.error("[ScriptGen] LLM returned no script content.")
                raise ValueError("LLM returned no script content.")
            if output_path is None:
                safe_task = task.lower().replace(' ', '_').replace('/', '_')[:40]
                output_path = str(Path("./generated") / f"selenium_{safe_task}.py")
            from ..tools.file_system_tools import save_text_to_file
            self.logger.debug(f"Saving Selenium script to {output_path}")
            save_text_to_file(output_path, script)
            self.logger.info(f"Selenium script generated at {output_path} via save_text_to_file")
            return str(Path(output_path).absolute())
        except Exception as e:
            self.logger.error(f"Failed to generate Selenium script: {e}")
            raise
    # async def replay_actions_with_playwright(...)
