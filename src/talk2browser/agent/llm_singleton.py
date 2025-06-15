# LLM Singleton for talk2browser
_llm = None

def set_llm(llm_instance):
    global _llm
    _llm = llm_instance

def get_llm():
    if _llm is None:
        raise RuntimeError("LLM singleton not initialized")
    return _llm
