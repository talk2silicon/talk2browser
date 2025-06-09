#!/usr/bin/env python3
"""Generate Playwright scripts from recorded actions using LLM."""
import json
import argparse
from typing import List, Dict, Any
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic

PROMPT_TEMPLATE = """You are an expert at writing Playwright scripts. Convert the following recorded actions into a clean, maintainable Playwright script.

Guidelines:
1. Use page.locator() for all element selections
2. Add comments to explain the purpose of each action
3. Include proper error handling
4. Add appropriate waits where necessary
5. Use async/await pattern
6. Include necessary imports and setup code
7. Add type hints for better IDE support
8. Include a main() function with proper cleanup

Actions:
{actions}

Generated script:"""

def load_recording(filepath: str) -> List[Dict[str, Any]]:
    """Load recorded actions from a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def generate_script(actions: List[Dict[str, Any]], model_name: str = "claude-3-opus-20240229") -> str:
    """Generate a Playwright script from recorded actions using LLM.
    
    Args:
        actions: List of recorded actions
        model_name: Name of the LLM model to use
        
    Returns:
        Generated Playwright script as a string
    """
    # Format actions for the prompt
    formatted_actions = []
    for i, action in enumerate(actions, 1):
        formatted_actions.append(
            f"{i}. {action['tool']}: {json.dumps(action['args'], indent=2, default=str)}"
        )
    
    # Initialize the LLM
    llm = ChatAnthropic(
        model=model_name,
        temperature=0.1,
        max_tokens=4000
    )
    
    # Create the prompt
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | llm | StrOutputParser()
    
    # Generate the script
    script = chain.invoke({"actions": "\n".join(formatted_actions)})
    
    # Clean up the script (remove markdown code blocks if present)
    script = script.replace('```python', '').replace('```', '').strip()
    
    return script

def save_script(script: str, output_path: str) -> None:
    """Save the generated script to a file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(script)
    
    print(f"Script saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Generate Playwright script from recorded actions')
    parser.add_argument('input_file', help='Input JSON file with recorded actions')
    parser.add_argument('-o', '--output', default='generated_script.py',
                       help='Output Python file (default: generated_script.py)')
    parser.add_argument('--model', default='claude-3-opus-20240229',
                       help='LLM model to use (default: claude-3-opus-20240229)')
    
    args = parser.parse_args()
    
    try:
        # Load recorded actions
        actions = load_recording(args.input_file)
        
        # Generate the script
        print(f"Generating Playwright script using {args.model}...")
        script = generate_script(actions, args.model)
        
        # Save the script
        save_script(script, args.output)
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
