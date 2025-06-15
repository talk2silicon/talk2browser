import os
import logging
from typing import Optional, List
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

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
