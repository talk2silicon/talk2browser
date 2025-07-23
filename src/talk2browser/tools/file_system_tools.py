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

def compress_image_to_size_limit(path, max_size=4.5 * 1024 * 1024, min_quality=15, resize_factor=0.75):
    """
    Compress an image to ensure it is below the specified size limit (in bytes).
    Returns a BytesIO object with the compressed image data.
    """
    import io
    from PIL import Image
    with Image.open(path) as img:
        quality = 80
        compressed_img = io.BytesIO()
        img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
        # Reduce quality if needed
        while compressed_img.tell() > max_size and quality > min_quality:
            quality -= 10
            logger.debug(f"[FileSystemTools] Reducing image quality to {quality} to meet size limit")
            compressed_img = io.BytesIO()
            img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
        # If still too large, resize the image
        if compressed_img.tell() > max_size:
            width, height = img.size
            resize_factor_current = resize_factor
            while compressed_img.tell() > max_size and resize_factor_current > 0.3:
                new_width = int(width * resize_factor_current)
                new_height = int(height * resize_factor_current)
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                logger.debug(f"[FileSystemTools] Resizing image to {new_width}x{new_height} to meet size limit")
                compressed_img = io.BytesIO()
                resized_img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
                if compressed_img.tell() > max_size:
                    resize_factor_current -= 0.15
                else:
                    break
                if new_width < 100 or new_height < 100:
                    logger.warning("[FileSystemTools] Image too small after resizing; cannot compress further.")
                    break
                logger.debug(f"[FileSystemTools] Resized image to {resize_factor_current:.2f}x original size to meet size limit")
        compressed_img.seek(0)
        img_bytes = compressed_img.read()
        # Final size check - if still too large, use extreme measures
        if len(img_bytes) > max_size:
            logger.warning(f"[FileSystemTools] Image still too large ({len(img_bytes)/1024/1024:.2f}MB), using grayscale conversion")
            gray_img = img.convert('L')  # Convert to grayscale
            compressed_img = io.BytesIO()
            gray_img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
            compressed_img.seek(0)
        return compressed_img

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
