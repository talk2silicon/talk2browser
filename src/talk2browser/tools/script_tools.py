import os
import json
import logging
from typing import Optional, List
from langchain_core.tools import tool
from ..agent.action_recorder_singleton import recorder
from langchain_anthropic import ChatAnthropic
from ..agent.llm_singleton import get_llm

logger = logging.getLogger(__name__)

@tool
def generate_script(language: str, task: str, prompt: Optional[str] = None) -> str:
    """
    Generate a test script (Playwright, Cypress, Selenium, etc.) from the in-memory recorded actions.
    Args:
        language: The target automation framework ('playwright', 'cypress', 'selenium').
        task: The scenario/task description.
        prompt: Optional, custom LLM prompt.
    Returns:
        Path to the generated script file.
    """
    actions = recorder.actions
    if not actions:
        logger.error("No actions recorded in memory for script generation.")
        raise ValueError("No actions recorded.")

    # Choose prompt template
    if prompt:
        llm_prompt = prompt
    else:
        if language.lower() == 'playwright':
            llm_prompt = (
                "Generate a Playwright Python script for the following scenario: "
                f"{task}\nActions: {json.dumps(actions, indent=2)}\n"
                "Only output the code, no markdown or explanation."
            )
        elif language.lower() == 'cypress':
            llm_prompt = (
                "Generate a Cypress JavaScript test script for the following scenario: "
                f"{task}\nActions: {json.dumps(actions, indent=2)}\n"
                "Only output the code, no markdown or explanation."
            )
        elif language.lower() == 'selenium':
            llm_prompt = (
                "Generate a Selenium Python script for the following scenario: "
                f"{task}\nActions: {json.dumps(actions, indent=2)}\n"
                "Only output the code, no markdown or explanation."
            )
        else:
            logger.error(f"Unsupported language: {language}")
            raise ValueError(f"Unsupported language: {language}")

    llm = get_llm()
    logger.info(f"[GEN_SCRIPT] Calling LLM to generate {language} script for scenario: {task}")
    logger.debug(f"[GEN_SCRIPT] Actions for script generation: {json.dumps(actions, indent=2)}")
    logger.debug(f"[GEN_SCRIPT] LLM prompt: {llm_prompt}")

    try:
        response = llm.invoke(llm_prompt)
        logger.debug(f"[GEN_SCRIPT] LLM response (first 200 chars): {repr(response)[:200]}")
    except Exception as e:
        logger.error(f"[GEN_SCRIPT] Error during LLM script generation: {e}", exc_info=True)
        response = None

    safe_task = task.lower().replace(' ', '_').replace('/', '_')[:40]
    script_ext = {
        'playwright': 'py',
        'cypress': 'cy.js',
        'selenium': 'selenium.py'
    }.get(language.lower(), 'txt')
    script_path = os.path.join('generated', f"generated_script_{safe_task}.{script_ext}")

    # Ensure output directory exists before saving
    # Extract string content from LLM response if needed
    script_content = response
    if not isinstance(response, str):
        # Try extracting .content or .text for known message types
        script_content = getattr(response, 'content', None) or getattr(response, 'text', None)
        if script_content is None:
            logger.error(f"[GEN_SCRIPT] LLM response is not a string and has no .content/.text attribute. Type: {type(response)}. Value: {repr(response)}")
            return None
        logger.debug(f"[GEN_SCRIPT] Extracted script content from response object: {type(response)}")

    try:
        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        logger.info(f"[GEN_SCRIPT] Saving script to {script_path}")
        logger.debug(f"[GEN_SCRIPT] Script content (first 200 chars): {repr(script_content)[:200]}")
        if script_content and script_content.strip():
            with open(script_path, 'w') as f:
                f.write(script_content)
            logger.info(f"[GEN_SCRIPT] Generated {language} script saved to {script_path}")
            return script_path
        else:
            logger.error(f"[GEN_SCRIPT] Script generation failed or returned empty response. Script not saved for scenario '{task}'.")
            return None
    except Exception as file_exc:
        logger.error(f"[GEN_SCRIPT] Failed to save script to {script_path}: {file_exc}")
        return None


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
    actions = recorder.actions
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

