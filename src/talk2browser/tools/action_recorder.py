import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

class ActionRecorder:
    """Records browser tool actions and generates Playwright scripts and logs."""
    def __init__(self):
        self.actions: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
        self.base_name: Optional[str] = None  # Used for consistent file naming

    async def generate_cypress_script(self, llm, task: str) -> str:
        """Generate a Cypress script from recorded actions using LLM and set consistent base name."""
        if not self.actions:
            raise ValueError("No recorded actions found")

        # Format actions for the prompt
        formatted_actions = []
        for i, action in enumerate(self.actions, 1):
            formatted_actions.append(f"{i}. {action['command']}")

        # Cypress LLM Prompt
        prompt = (
            "You are an expert at writing Cypress end-to-end tests.\n"
            "Convert the following recorded browser actions into a clean, maintainable Cypress test script.\n\n"
            "IMPORTANT: Only output the raw JavaScript code, without any markdown formatting, explanations, or additional text.\n"
            "The output should be a complete, runnable Cypress test file (e.g., .cy.js) that can be executed directly.\n\n"
            "Guidelines:\n"
            "1. Add proper Cypress imports and describe/it blocks.\n"
            "2. Add comments to explain the purpose of each action.\n"
            "3. Use cy.visit, cy.get, cy.type, cy.click, cy.check, cy.uncheck, cy.select, etc. as appropriate.\n"
            "4. Add human-like delays between actions using cy.wait(500).\n"
            "5. Do not include any markdown formatting (```js or ``` or ```javascript)\n"
            "6. Do not include any explanations or additional text outside the script.\n\n"
            "Here are the recorded browser commands (in Playwright-style):\n"
            "{actions}\n\n"
            "Generate ONLY the JavaScript code, with no additional text or formatting.\n"
            "Add cy.wait(500) between actions for better visibility."
        )

        # Generate a unique output path and base name based on timestamp and prompt/task
        import re
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        words = re.findall(r'\w+', task)[:8]
        prompt_snippet = '_'.join(words).lower()
        self.base_name = f"generated_script_{timestamp}_{prompt_snippet}"
        filename = f"{self.base_name}.cy.js"
        output_path = str(Path("./generated") / filename)
        self.logger.debug(f"[Cypress] Using base name for files: {self.base_name}")

        # Use LLM to generate script
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            chain = ChatPromptTemplate.from_template(prompt) | llm | StrOutputParser()
            script = await chain.ainvoke({"actions": "\n".join(formatted_actions)})
            script = script.strip()
            # Remove markdown code block markers if present
            if script.startswith('```javascript'):
                script = script[13:]
            elif script.startswith('```js'):
                script = script[5:]
            elif script.startswith('```'):
                script = script[3:]
            if script.endswith('```'):
                script = script[:-3]
            script = script.split('Explanation:')[0].strip()
            script = script.rstrip() + '\n'
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(script, encoding='utf-8')
            self.logger.info(f"Cypress script generated at {output_path}")
            # Save actions to JSON with same base name
            self.to_json()
            self.clear()
            return str(Path(output_path).absolute())
        except Exception as e:
            self.logger.error(f"Failed to generate Cypress script: {e}")
            raise

    def record_action(self, tool: str, args: Dict[str, Any], command: str, screenshot_path: Optional[str] = None) -> None:
        self.logger.debug(f"Recording action: {tool} {args}")
        self.actions.append({
            'tool': tool,
            'args': args,
            'command': command,
            'timestamp': self._get_time(),
            'screenshot_path': screenshot_path
        })

    def to_json(self, filepath: Optional[str] = None) -> str:
        """Save actions to JSON file using consistent base name if not specified."""
        if not filepath:
            if not self.base_name:
                raise ValueError("Base name not set for action log file.")
            filepath = str(Path("./generated") / f"{self.base_name}.json")
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.actions, f, indent=2)
        self.logger.info(f"Action log saved to {filepath}")
        return str(Path(filepath).absolute())

    def clear(self) -> None:
        self.actions.clear()

    async def generate_playwright_script(self, llm, task: str) -> str:
        """Generate a Playwright script from recorded actions using LLM and set consistent base name."""
        if not self.actions:
            raise ValueError("No recorded actions found")
        
        # Format actions for the prompt
        formatted_actions = []
        for i, action in enumerate(self.actions, 1):
            formatted_actions.append(f"{i}. {action['command']}")

        # Prompt for LLM
        prompt = ("You are an expert at writing Playwright scripts.\n"
                  "Convert the following recorded actions into a clean, maintainable Playwright script.\n\n"
                  "IMPORTANT: Only output the raw Python code, without any markdown formatting, explanations, or additional text.\n"
                  "The output should be a complete, runnable Python script that can be executed directly.\n\n"
                  "Guidelines:\n"
                  "1. Add proper imports and setup code\n"
                  "2. Add comments to explain the purpose of each action\n"
                  "3. Include proper error handling with descriptive error messages\n"
                  "4. Add human-like delays between actions using `asyncio.sleep()` for better visibility\n"
                  "5. Use async/await pattern\n"
                  "6. Add type hints for better IDE support\n"
                  "7. Include a main() function with proper cleanup\n"
                  "8. Set browser to run in non-headless mode (visible) by default\n"
                  "9. Add a small delay (0.5-1 second) between actions for better visibility\n"
                  "10. Do not include any markdown formatting (```python or ``` or ```python3)\n\n"
                  "11. Do not include any explanations or additional text outside the script\n\n"
                  "Here are the recorded Playwright commands:\n"
                  "{actions}\n\n"
                  "Generate ONLY the Python code, with no additional text or formatting.\n"
                  "Make sure to include `headless=False` when launching the browser.\n"
                  "Add `asyncio.sleep(0.5)` between actions for better visibility.")

        # Generate a unique output path and base name based on timestamp and prompt/task
        import re
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        words = re.findall(r'\w+', task)[:8]
        prompt_snippet = '_'.join(words).lower()
        self.base_name = f"generated_script_{timestamp}_{prompt_snippet}"
        filename = f"{self.base_name}.py"
        output_path = str(Path("./generated") / filename)
        self.logger.debug(f"Using base name for files: {self.base_name}")

        # Use LLM to generate script
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            chain = ChatPromptTemplate.from_template(prompt) | llm | StrOutputParser()
            script = await chain.ainvoke({"actions": "\n".join(formatted_actions)})
            script = script.strip()
            # Remove markdown code block markers if present
            if script.startswith('```python'):
                script = script[9:]
            elif script.startswith('```'):
                script = script[3:]
            if script.endswith('```'):
                script = script[:-3]
            script = script.split('Explanation:')[0].strip()
            script = script.rstrip() + '\n'
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(script, encoding='utf-8')
            self.logger.info(f"Playwright script generated at {output_path}")
            # Save actions to JSON with same base name
            self.to_json()
            self.clear()
            return str(Path(output_path).absolute())
        except Exception as e:
            self.logger.error(f"Failed to generate Playwright script: {e}")
            raise

    def update_screenshot_path(self, action_index: int, screenshot_path: str) -> None:
        """Update the screenshot_path for a specific action by index."""
        if 0 <= action_index < len(self.actions):
            self.actions[action_index]['screenshot_path'] = screenshot_path
            self.logger.debug(f"Updated screenshot_path for action {action_index}: {screenshot_path}")
        else:
            self.logger.error(f"Invalid action_index {action_index} for screenshot_path update.")

    def _get_time(self) -> float:
        import time
        return time.time()
