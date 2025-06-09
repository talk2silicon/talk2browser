"""Tests for Playwright script generation."""
import os
import asyncio
import pytest
from pathlib import Path
from langchain_anthropic import ChatAnthropic

from talk2browser.agent.agent import BrowserAgent
from talk2browser.tools.registry import ToolRegistry

@pytest.mark.asyncio
async def test_script_generation(tmp_path):
    """Test generating a Playwright script from recorded actions."""
    # Setup
    output_script = tmp_path / "test_script.py"
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",  # Use a faster model for testing
        temperature=0.1,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Mock tool registry with recorded actions
    tool_registry = ToolRegistry(llm=llm)
    tool_registry._recording = [
        {
            "tool": "navigate",
            "args": {"url": "https://example.com"},
            "timestamp": 0.0
        },
        {
            "tool": "click",
            "args": {"selector": "button"},
            "timestamp": 1.0
        }
    ]
    
    # Generate the script
    script_path = await tool_registry.generate_playwright_script(
        output_path=str(output_script)
    )
    
    # Verify the script was created
    assert os.path.exists(script_path)
    assert "example.com" in output_script.read_text()
    
    # Clean up
    if os.path.exists(script_path):
        os.remove(script_path)

@pytest.mark.asyncio
async def test_script_generation_no_actions():
    """Test script generation with no recorded actions."""
    tool_registry = ToolRegistry()
    
    with pytest.raises(ValueError, match="No recorded actions"):
        await tool_registry.generate_playwright_script("test.py")

if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__] + sys.argv[1:]))
