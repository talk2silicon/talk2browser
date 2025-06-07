"""Tests for browser module."""
import pytest


@pytest.mark.asyncio
async def test_playwright_client_initialization(browser):
    """Test that the Playwright client initializes correctly."""
    assert browser is not None
    assert browser.page is not None


@pytest.mark.asyncio
async def test_navigation(browser):
    """Test basic navigation."""
    await browser.page.goto("https://example.com")
    assert "Example Domain" in await browser.page.title()
