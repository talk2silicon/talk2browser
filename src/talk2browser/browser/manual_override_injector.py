import os
from playwright.async_api import Page

MANUAL_OVERRIDE_JS_PATH = os.path.join(os.path.dirname(__file__), '../../examples/manual_override.js')

async def inject_manual_override(page: Page):
    """
    Inject the manual_override.js script into the page for manual/agent mode toggling and manual action recording.
    """
    with open(MANUAL_OVERRIDE_JS_PATH, 'r', encoding='utf-8') as f:
        js_code = f.read()
    await page.add_init_script(js_code)

async def set_manual_mode(page: Page):
    """
    Switch the UI to manual mode (user recording).
    """
    await page.evaluate("window.setManualMode && window.setManualMode()")

async def set_agent_mode(page: Page):
    """
    Switch the UI to agent mode (automation running).
    """
    await page.evaluate("window.setAgentMode && window.setAgentMode()")

async def get_manual_actions(page: Page):
    """
    Retrieve the recorded manual actions as JSON from the browser context.
    """
    return await page.evaluate("window.getManualActions && window.getManualActions()")

async def save_manual_actions(page: Page, output_path: str):
    """
    Save the recorded manual actions to a JSON file.
    """
    actions = await get_manual_actions(page)
    import json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(actions, f, indent=2)
    return output_path
