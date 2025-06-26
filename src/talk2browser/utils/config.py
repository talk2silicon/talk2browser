import os
import toml
from pathlib import Path
import logging

_config = None

def get_t2b_config():
    global _config
    if _config is not None:
        return _config
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        data = toml.load(pyproject_path)
        _config = data.get("tool", {}).get("talk2browser", {})
    else:
        _config = {}
    return _config

def is_vision_enabled():
    # Environment variable takes precedence
    env_val = os.getenv("VISION_ENABLED")
    if env_val is not None:
        try:
            val = env_val.lower()
            enabled = val in ("1", "true", "yes", "on")
            logging.getLogger(__name__).info(f"[config] VISION_ENABLED from env: {env_val} -> {enabled}")
            return enabled
        except Exception as e:
            logging.getLogger(__name__).warning(f"[config] Error parsing VISION_ENABLED env: {e}")
    # Fall back to pyproject.toml
    enabled = bool(get_t2b_config().get("vision_enabled", False))
    logging.getLogger(__name__).info(f"[config] VISION_ENABLED from pyproject.toml: {enabled}")
    return enabled

def get_vision_model_path():
    return get_t2b_config().get("vision_model_path", "./models/yolo11s.pt")
