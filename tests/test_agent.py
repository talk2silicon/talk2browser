"""Tests for agent module."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from talk2browser.agent.agent import BrowserAgent
from langchain_core.messages import HumanMessage

@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    mock = AsyncMock()
    mock.ainvoke.return_value = "Mock response"
    return mock

@pytest.fixture
async def agent(mock_llm):
    """Create a test agent with a mock LLM."""
    async with BrowserAgent(llm=mock_llm, headless=True) as agent:
        # Mock the client and page
        agent.client = AsyncMock()
        agent.client.page = AsyncMock()
        agent.client.page.url = "http://example.com"
        agent.client.page.title = AsyncMock(return_value="Example Page")
        agent.client.get_page_state = AsyncMock(return_value={
            "url": "http://example.com",
            "title": "Example Page"
        })
        
        # Set up the page for browser tools
        from talk2browser.tools.browser_tools import BrowserTools
        BrowserTools.set_page(agent.client.page)
        
        yield agent

@pytest.mark.asyncio
async def test_agent_initialization(agent):
    """Test that the agent initializes correctly."""
    assert agent is not None
    assert hasattr(agent, 'tool_node')
    assert agent.client is not None

@pytest.mark.asyncio
async def test_agent_run(agent, mock_llm):
    """Test running the agent with a simple prompt."""
    # Setup mock response
    mock_llm.ainvoke.return_value = HumanMessage(content="Navigated to example.com")
    
    # Run the agent
    result = await agent.run("Navigate to example.com")
    
    # Verify results
    assert result is not None
    assert "Navigated to example.com" in result
    agent.client.page.goto.assert_awaited_once_with("http://example.com")
