# src/talk2browser/services/sensitive_data_service.py
import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class SensitiveDataService:
    """
    Centralized service for managing sensitive data (secrets).
    Supports runtime dictionary and environment variables.
    Singleton pattern for global access within the process.
    """
    _instance = None

    def __init__(self, secrets: Optional[Dict[str, str]] = None):
        self._secrets = secrets or {}
        logger.debug(f"SensitiveDataService initialized with keys: {list(self._secrets.keys())}")

    @classmethod
    def configure(cls, secrets: Optional[Dict[str, str]] = None):
        """Configure the singleton instance with a new secret dict."""
        cls._instance = cls(secrets)
        logger.debug(f"SensitiveDataService configured with keys: {list((secrets or {}).keys())}")
        logger.debug(f"[SensitiveDataService.configure] id={id(cls._instance)} keys={list(cls._instance._secrets.keys())}")

    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret by key, searching runtime secrets first, then environment variables."""
        if cls._instance is None:
            logger.warning("SensitiveDataService.get() called before configuration. Returning None.")
            return os.environ.get(key, default)
        logger.debug(f"[SensitiveDataService.get] id={id(cls._instance)} keys={list(cls._instance._secrets.keys())} lookup={key}")
        val = cls._instance._secrets.get(key)
        if val is not None:
            logger.debug(f"Secret '{key}' resolved from runtime secrets.")
            return val
        env_val = os.environ.get(key, default)
        if env_val is not None:
            logger.debug(f"Secret '{key}' resolved from environment variables.")
        else:
            logger.warning(f"Secret '{key}' not found in secrets or environment.")
        return env_val

    @classmethod
    def clear(cls):
        """Clear the singleton instance (for tests or cleanup)."""
        cls._instance = None
        logger.debug("SensitiveDataService cleared.")
