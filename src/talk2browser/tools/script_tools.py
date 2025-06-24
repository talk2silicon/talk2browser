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
    actions = action_service.actions
    logger.info(f"[ScriptTools] Using canonical merged actions for script generation: {json.dumps(actions, indent=2)}")
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
    actions = action_service.actions
    logger.info(f"[ScriptTools] Using canonical merged actions for negative test generation: {json.dumps(actions, indent=2)}")
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

from langchain_core.tools import tool
import json, os, re, logging, asyncio

@tool
async def replay_action_json_with_playwright(action_json_path: str) -> str:
    """
    Backend-agnostic replay of browser actions from a JSON file using Playwright.
    Only 'type' and 'args' fields are required in each action.
    Args:
        action_json_path: Path to the action JSON file.
        headless: Run browser in headless mode (default False).
    Returns:
        Result summary string.
    """
    logger = logging.getLogger(__name__)
    from ..browser.page_manager import PageManager

    if not os.path.isfile(action_json_path):
        logger.error(f"Action JSON not found: {action_json_path}")
        return f"Error: Action JSON not found: {action_json_path}"

    with open(action_json_path) as f:
        data = json.load(f)
    actions = data['actions'] if 'actions' in data else data
    logger.info(f"[REPLAY] Loaded actions: {json.dumps(actions, indent=2)}")

    page_manager = PageManager.get_instance()
    browser_page = page_manager.get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return "Error: No active browser page."
    page = browser_page.get_page()

    def resolve_placeholders(val):
        if not isinstance(val, str):
            return val
        def repl(match):
            var = match.group(1)
            env_val = os.environ.get(var)
            if env_val is not None:
                logger.info(f"[REPLAY] Replacing placeholder ${{{var}}} with env value.")
                return env_val
            logger.warning(f"[REPLAY] No env value found for ${{{var}}}, leaving as is.")
            return match.group(0)
        return re.sub(r"\$\{(\w+)\}", repl, val)

    def get_playwright_selector(args):
        # Prefer css_selector if present and non-empty
        if 'css_selector' in args and args['css_selector']:
            logger.info(f"[REPLAY] Using css_selector: {args['css_selector']}")
            return args['css_selector']
        selector = args.get('selector')
        if not selector:
            logger.warning("[REPLAY] No selector found in args.")
            return None
        # Heuristic: XPath usually starts with '/' or 'html/'
        if selector.strip().startswith('/') or selector.strip().startswith('html/'):
            logger.info(f"[REPLAY] Detected XPath selector, using xpath={selector}")
            return f"xpath={selector}"
        logger.info(f"[REPLAY] Using selector as CSS: {selector}")
        return selector

    for idx, action in enumerate(actions):
        try:
            logger.info(f"[REPLAY] -------- Action {idx} --------")
            logger.info(f"[REPLAY] Raw action: {action}")
            if not isinstance(action, dict) or 'type' not in action or 'args' not in action:
                logger.error(f"Malformed action at index {idx}: {action}")
                return f"Error: Malformed action at index {idx}: {action}"
            action_type = action['type']
            args = action['args']
            resolved_args = {k: resolve_placeholders(v) for k, v in args.items()}
            logger.info(f"[REPLAY] Args after placeholder resolution: {resolved_args}")
            if action_type == 'navigate':
                url = resolved_args.get('url')
                logger.info(f"[REPLAY] Navigating to {url}")
                await page.goto(url)
                logger.info(f"[REPLAY] Navigated to {url}")
            elif action_type == 'click':
                selector = get_playwright_selector(resolved_args)
                logger.info(f"[REPLAY] Clicking selector: {selector}")
                await page.click(selector)
                logger.info(f"[REPLAY] Clicked {selector}")
            elif action_type == 'fill':
                selector = get_playwright_selector(resolved_args)
                value = resolved_args.get('text') or resolved_args.get('value')
                logger.info(f"[REPLAY] Filling selector: {selector} with value: {value}")
                await page.fill(selector, value)
                logger.info(f"[REPLAY] Filled {selector} with {value}")
            else:
                logger.error(f"Unknown action type at index {idx}: {action_type}")
                return f"Error: Unknown action type '{action_type}' at index {idx}."
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"[REPLAY] Exception on action {idx}: {action}")
            logger.error(f"[REPLAY] Exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Error: Failed on action {idx}: {action} - {e}"
    logger.info(f"[REPLAY] Successfully replayed {len(actions)} actions from {action_json_path}")
    return f"Successfully replayed {len(actions)} actions from {action_json_path}"

