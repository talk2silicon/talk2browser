"""Tools module for talk2browser."""

from .browser_tools import (
    navigate,
    click,
    fill,
    get_count,
    is_enabled,
    list_interactive_elements,
    list_suggestions,
    generate_pdf_from_html,
    extract_structured_data,
)
from .script_tools import (
    generate_script,
    generate_negative_tests,
    replay_action_json_with_playwright,
    load_test_data,
)
from .file_system_tools import list_files_in_folder
from .custom_tools import set_code_in_editor, save_json

__all__ = [
    "navigate",
    "click",
    "fill",
    "get_count",
    "is_enabled",
    "list_interactive_elements",
    "list_suggestions",
    "generate_pdf_from_html",
    "get_screenshot",
    "extract_structured_data",
    "generate_script",
    "generate_negative_tests",
    "replay_action_json_with_playwright",
    "load_test_data",
    "list_files_in_folder",
    "set_code_in_editor",
    "save_json",
]
