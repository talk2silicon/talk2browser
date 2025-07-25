# LLM Singleton for talk2browser
from typing import Any, Optional

_llm: Optional[Any] = None


def set_llm(llm_instance: Any) -> None:
    global _llm
    _llm = llm_instance


def get_llm() -> Any:
    if _llm is None:
        raise RuntimeError("LLM singleton not initialized")
    return _llm
