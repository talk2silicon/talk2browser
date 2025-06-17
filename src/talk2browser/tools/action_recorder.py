import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Import ActionService singleton or instance
from ..services.action_service import ActionService
# Singleton instance for now (could be moved to a dedicated singleton file if needed)
action_service = ActionService()

# DEPRECATED: This file is intentionally left empty. All action logic is now handled by ActionService.

