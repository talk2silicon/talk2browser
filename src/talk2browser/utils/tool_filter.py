"""Utility for filtering and ranking tools based on user input and page state."""
from typing import Dict, List, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

def filter_tools(
    user_input: str,
    tools: List[Dict[str, Any]],
    state: Dict[str, Any],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Filter and rank tools based on user input and page state using TF-IDF cosine similarity.
    
    Args:
        user_input: The user's input text
        tools: List of tool dictionaries to filter
        state: Current page state from browser
        top_k: Number of top matches to return
        
    Returns:
        List of filtered tools with similarity scores and metadata
    """
    if not tools or not user_input.strip():
        return []

    try:
        # 1. Prepare tool texts with state context
        tool_texts = []
        for tool in tools:
            # Include state information in the tool's text representation
            state_context = f"page_url: {state.get('url', '')} page_title: {state.get('title', '')}"
            if state.get('interactive_elements'):
                state_context += " interactive_elements_present"
            if state.get('has_form'):
                state_context += " form_present"
                
            # Combine tool metadata and state context
            params = " ".join(tool.get("parameters", {}).keys())
            tool_text = f"{tool['name']} {tool['description']} {params} {state_context}"
            tool_texts.append(tool_text.lower())
        
        # 2. Combine user input with page state for query
        query = f"{user_input} {state.get('url', '')} {state.get('title', '')}".lower()
        
        # 3. Calculate TF-IDF and cosine similarity
        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform([query] + tool_texts)
        
        query_vec = tfidf[0:1]
        tool_vecs = tfidf[1:]
        
        scores = cosine_similarity(query_vec, tool_vecs)[0]
        
        # 4. Return top-k tools with scores
        results = [
            {
                "tool": tool, 
                "score": float(score),
                "name": tool['name'],
                "description": tool['description']
            } 
            for tool, score in zip(tools, scores)
        ]
        
        # Sort by score (descending) and take top_k
        sorted_results = sorted(results, key=lambda x: -x["score"])
        
        # Log the top matches for debugging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Top tool matches:")
            for i, result in enumerate(sorted_results[:top_k], 1):
                logger.debug(f"{i}. {result['name']}: {result['score']:.3f} - {result['description']}")
        
        return sorted_results[:top_k]
        
    except Exception as e:
        logger.error(f"Error in tool filtering: {e}", exc_info=True)
        # Fallback: return first top_k tools with score 0
        return [{"tool": t, "score": 0.0, "name": t['name'], "description": t['description']} 
               for t in tools[:top_k]]
