import logging
from typing import Optional, List, Any
import json
import os
from langchain_core.tools import tool
# Use singleton getter everywhere; do not instantiate directly.
from langchain_anthropic import ChatAnthropic
from ..agent.llm_singleton import get_llm
from ..services.action_service import ActionService

action_service = ActionService.get_instance()

logger = logging.getLogger(__name__)




@tool
def generate_script(language: str, task: str, prompt: Optional[str] = None) -> str:
    """
    Generate a test script (Playwright, Cypress, Selenium, etc.) from the merged actions (manual+agent) in ActionService.
    Args:
        language: The target automation framework ('playwright', 'cypress', 'selenium').
        task: The scenario/task description.
        prompt: Optional, custom LLM prompt (ignored; now handled by ScriptGenerationService).
    Returns:
        Path to the generated script file.
    """
    from ..services.script_generation_service import ScriptGenerationService
    actions = action_service.get_merged_actions()
    if not actions:
        logger.error("No merged actions available in ActionService for script generation.")
        raise ValueError("No merged actions available.")
    llm = get_llm()
    script_service = ScriptGenerationService(llm=llm)
    logger.info(f"[ScriptTools] Generating {language} script for scenario: {task}")
    logger.debug(f"[ScriptTools] Actions for script generation: {json.dumps(actions, indent=2)}")
    if language.lower() == 'playwright':
        import asyncio
        return asyncio.run(script_service.generate_playwright_script(actions, task))
    elif language.lower() == 'cypress':
        import asyncio
        return asyncio.run(script_service.generate_cypress_script(actions, task))
    else:
        logger.error(f"Unsupported language: {language}")
        raise ValueError(f"Unsupported language: {language}")


@tool
def generate_negative_tests(language: str, prompt: str) -> List[str]:
    """
    Generate negative test scripts for the current scenario using a prompt.
    Args:
        language: The target automation framework.
        prompt: User/LLM-supplied negative scenario description.
    Returns:
        List of paths to generated negative test scripts.
    """
    actions = action_service.get_agent_actions()
    if not actions:
        logger.error("No actions recorded in memory for negative test generation.")
        raise ValueError("No actions recorded.")
    llm = get_llm()
    logger.info(f"Generating negative tests for scenario: {prompt}")
    llm_prompt = (
        f"Given the following user actions: {json.dumps(actions, indent=2)}\n"
        f"Generate negative test scripts in {language} that cover: {prompt}\n"
        "Only output the code, no markdown or explanation."
    )
    response = llm.invoke(llm_prompt)
    safe_prompt = prompt.lower().replace(' ', '_').replace('/', '_')[:40]
    script_ext = {
        'playwright': 'py',
        'cypress': 'cy.js',
        'selenium': 'selenium.py'
    }.get(language.lower(), 'txt')
    script_path = os.path.join('generated', f"negative_test_{safe_prompt}.{script_ext}")
    with open(script_path, 'w') as f:
        f.write(response)
    logger.info(f"Generated negative test script saved to {script_path}")
    return [script_path]

@tool
def replay_action_json_with_playwright(action_json_path: str, headless: bool = False) -> str:
    """
    Backend-agnostic replay of browser actions from a JSON file using Playwright.
    Only 'type' and 'args' fields are required in each action.
    Args:
        action_json_path: Path to the action JSON file.
        headless: Run browser in headless mode (default False).
    Returns:
        Result summary string.
    """
    from playwright.sync_api import sync_playwright
    import time
    logger.info(f"[REPLAY] Launching Playwright with headless={headless}")
    if not os.path.isfile(action_json_path):
        logger.error(f"Action JSON not found: {action_json_path}")
        raise FileNotFoundError(f"Action JSON not found: {action_json_path}")
    with open(action_json_path) as f:
        data = json.load(f)
    actions = data['actions'] if 'actions' in data else data
    logger.info(f"[REPLAY] Replaying {len(actions)} actions from {action_json_path}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        for idx, action in enumerate(actions):
            try:
                if not isinstance(action, dict) or 'type' not in action or 'args' not in action:
                    logger.error(f"Malformed action at index {idx}: {action} - missing 'type' or 'args' field.")
                    browser.close()
                    return f"Error: Malformed action at index {idx}: {action} - missing 'type' or 'args' field. Please ensure all actions are valid and include 'type' and 'args' keys."
                action_type = action['type']
                args = action['args']
                logger.debug(f"[REPLAY] Action {idx}: type={action_type}, args={args}")
                if action_type == 'navigate':
                    page.goto(args['url'])
                elif action_type == 'click':
                    page.click(args['selector'])
                elif action_type == 'fill':
                    page.fill(args['selector'], args['value'])
                else:
                    logger.error(f"Unknown action type at index {idx}: {action_type}")
                    browser.close()
                    return f"Error: Unknown action type '{action_type}' at index {idx}."
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed on action {idx}: {action} - {e}")
                browser.close()
                return f"Error: Failed on action {idx}: {action} - {e}"
        browser.close()
    return f"Successfully replayed {len(actions)} actions from {action_json_path}"

