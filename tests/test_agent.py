"""Tests for agent module."""
import pytest


@pytest.mark.asyncio
async def test_agent_initialization(agent):
    """Test that the agent initializes correctly."""
    assert agent is not None
    assert agent.tool_registry is not None


@pytest.mark.asyncio
async def test_agent_run(agent):
    """Test running the agent with a simple prompt."""
    # This is a simple test that just verifies the agent runs without errors
    # More comprehensive tests will be added as the agent implementation grows
    result = await agent.run("Navigate to example.com")
    assert result is not None
