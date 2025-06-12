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

    def record_action(self, tool: str, args: Dict[str, Any], command: str) -> None:
        self.logger.debug(f"Recording action: {tool} {args}")
        self.actions.append({
            'tool': tool,
            'args': args,
            'command': command,
            'timestamp': self._get_time()
        })

    def to_json(self, filepath: str) -> None:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.actions, f, indent=2)
        self.logger.info(f"Action log saved to {filepath}")

    def clear(self) -> None:
        self.actions.clear()

    async def generate_playwright_script(self, output_path: str, llm) -> str:
        """Generate a Playwright script from recorded actions using LLM."""
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
            self.clear()
            return str(Path(output_path).absolute())
        except Exception as e:
            self.logger.error(f"Failed to generate Playwright script: {e}")
            raise

    def _get_time(self) -> float:
        import time
        return time.time()
