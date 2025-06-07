"""Pytest configuration and fixtures for talk2browser tests."""
import pytest
from typing import AsyncGenerator

from talk2browser.agent import BrowserAgent
from talk2browser.browser import PlaywrightClient


@pytest.fixture
def tool_registry():
    """Fixture providing a tool registry."""
    from talk2browser.tools import ToolRegistry
    return ToolRegistry()


@pytest.fixture
async def browser() -> AsyncGenerator[PlaywrightClient, None]:
    """Fixture providing a Playwright browser instance."""
    async with PlaywrightClient(headless=True) as browser:
        yield browser


@pytest.fixture
async def agent() -> AsyncGenerator[BrowserAgent, None]:
    """Fixture providing a BrowserAgent instance."""
    async with BrowserAgent(headless=True) as agent:
        yield agent
