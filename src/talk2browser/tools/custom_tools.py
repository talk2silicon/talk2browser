"""Custom tools that extend beyond basic Playwright functionality."""

import logging
from langchain.tools import tool
from ..browser.page_manager import PageManager

@tool
async def set_code_in_editor(selector: str, code: str) -> str:
    """
    Set code in a web-based code editor (Ace, Monaco, CodeMirror, etc.).
    Args:
        selector: CSS selector for the editor container (e.g., '.ace_editor', '.monaco-editor', etc.)
        code: The code string to inject into the editor.
    Returns:
        str: Confirmation message or error details.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"TOOL CALL: set_code_in_editor(selector={selector}, code=<omitted>)")
    browser_page = PageManager.get_instance().get_current_page()
    if not browser_page:
        logger.error("No active browser page found in PageManager.")
        return f"Error: No active browser page."
    page = browser_page.get_page()
    try:
        result = await page.evaluate(
            '''({selector, code}) => {
                const el = document.querySelector(selector);
                if (!el) throw new Error('Editor not found for selector: ' + selector);
                // Ace Editor
                if (window.ace && el.classList.contains('ace_editor')) {
                    window.ace.edit(el).setValue(code, -1);
                    return 'ace';
                }
                // Monaco Editor
                if (window.monaco && el.classList.contains('monaco-editor')) {
                    if (window.monaco.editor && window.monaco.editor.getEditors) {
                        const editors = window.monaco.editor.getEditors();
                        const editor = Array.from(editors).find(e => e.getDomNode() === el);
                        if (editor) {
                            editor.setValue(code);
                            return 'monaco';
                        }
                    }
                }
                // CodeMirror (v5)
                if (window.CodeMirror && el.CodeMirror) {
                    el.CodeMirror.setValue(code);
                    return 'codemirror';
                }
                // CodeMirror (v6+)
                if (el.cmView && el.cmView.state && el.cmView.dispatch) {
                    el.cmView.dispatch({
                        changes: {from: 0, to: el.cmView.state.doc.length, insert: code}
                    });
                    return 'codemirror6';
                }
                throw new Error('Unsupported or undetected editor type for selector: ' + selector);
            }''',
            {"selector": selector, "code": code}
        )
        logger.info(f"Injected code using editor type: {result}")
        return f"Successfully set code in {result} editor using selector '{selector}'."
    except Exception as e:
        logger.error(f"Failed to set code in editor: {e}")
        return f"Error: Failed to set code in editor: {e}"

from langchain.tools import tool

@tool
def save_json(data: dict, filename: str) -> str:
    """
    Save a Python dictionary as a JSON file with the given filename.
    Args:
        data: The dictionary to save.
        filename: The filename (including .json) to save to.
    Returns:
        str: The path to the saved file.
    """
    import json
    import os
    logger = logging.getLogger(__name__)
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved JSON to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save JSON to {filename}: {e}")
        return f"Error: {e}"
