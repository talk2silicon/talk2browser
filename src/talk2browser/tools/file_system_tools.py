import os
import logging
from typing import Optional, List
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def save_json_to_file(path: str, data) -> None:
    """
    Save data as JSON to the given file path, creating parent directories if needed.
    Args:
        path: Path to the JSON file to write.
        data: Data to serialize as JSON.
    """
    import json
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved JSON to {path}")

def save_text_to_file(path: str, text: str) -> None:
    """
    Save plain text to the given file path, creating parent directories if needed.
    Args:
        path: Path to the text file to write.
        text: Text content to write.
    """
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    logger.info(f"Saved text file to {path}")

@tool
def list_files_in_folder(folder_path: str, extension_filter: Optional[str] = None) -> List[str]:
    """
    List files in a folder, optionally filtered by extension.
    Args:
        folder_path: Directory to list files from.
        extension_filter: e.g., '.json' to only list JSON files.
    Returns:
        List of file paths (relative to folder_path).
    """
    if not os.path.isdir(folder_path):
        logger.error(f"Folder not found: {folder_path}")
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    files = os.listdir(folder_path)
    if extension_filter:
        files = [f for f in files if f.endswith(extension_filter)]
    logger.info(f"Found {len(files)} files in {folder_path} with filter {extension_filter}")
    return [os.path.join(folder_path, f) for f in files]
