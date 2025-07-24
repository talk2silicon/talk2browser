import os
import re
import logging

from talk2browser.services.sensitive_data_service import SensitiveDataService

def resolve_secret_placeholders(value):
    """
    Resolves secret placeholders in a string using SensitiveDataService.
    Only resolves if value matches ${VAR}. Otherwise, returns as-is.
    """
    logger = logging.getLogger(__name__)
    if not isinstance(value, str):
        return value
    # Only resolve if value matches ${VAR}
    import re
    pattern = r"^\$\{([A-Z0-9_]+)\}$"
    match = re.fullmatch(pattern, value)
    if match:
        var_name = match.group(1)
        svc = getattr(SensitiveDataService, "_instance", None)
        if svc is None:
            logger.debug("[resolve_secret_placeholders] SensitiveDataService._instance is None!")
            return value
        secret = svc.get(var_name)
        if secret is not None:
            logger.debug(f"Resolved secret for env var '{var_name}' via SensitiveDataService.")
            return secret
        else:
            logger.warning(f"Secret '{var_name}' not found in SensitiveDataService.")
    # For all other cases, just return the value as-is (do not warn)
    return value
