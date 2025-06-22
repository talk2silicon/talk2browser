import os
import re
import logging

from talk2browser.services.sensitive_data_service import SensitiveDataService

def resolve_secret_placeholders(value):
    """
    Resolves secret placeholders in a string using SensitiveDataService.
    - If value matches a key in SensitiveDataService, use it.
    - If value contains ${VAR}, replace with SensitiveDataService.get(VAR).
    - If not found, return as-is.
    """
    logger = logging.getLogger(__name__)
    # Only resolve strings
    if not isinstance(value, str):
        return value
    # Match ${VAR_NAME} or plain key
    if value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
    else:
        key = value
    # Debug log singleton state
    svc = getattr(SensitiveDataService, "_instance", None)
    if svc is None:
        logger.debug("[resolve_secret_placeholders] SensitiveDataService._instance is None!")
        return value
    logger.debug(f"[resolve_secret_placeholders] id={id(svc)} keys={list(getattr(svc, '_secrets', {}).keys())} resolving {key}")
    # Direct key lookup
    secret = svc.get(key)
    if secret is not None:
        logger.debug(f"Resolved secret for key '{value}' from SensitiveDataService.")
        return secret
    # Pattern: ${VAR_NAME}
    import re
    pattern = r"\$\{([A-Z0-9_]+)\}"
    match = re.fullmatch(pattern, value or "")
    if match:
        var_name = match.group(1)
        secret = SensitiveDataService.get(var_name)
        if secret is not None:
            logger.debug(f"Resolved secret for env var '{var_name}' via SensitiveDataService.")
            return secret
        else:
            logger.warning(f"Secret '{var_name}' not found in SensitiveDataService.")
    return value
