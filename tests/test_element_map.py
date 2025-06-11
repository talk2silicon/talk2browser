"""
Test script to verify the element map is properly populated and used by browser tools.
"""
import asyncio
import logging
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.talk2browser.agent.agent import BrowserAgent
from src.talk2browser.browser.dom.service import DOMService
from src.talk2browser.browser import PlaywrightClient
from src.talk2browser.tools.browser_tools import navigate, click, set_page

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_element_map():
    """Test that the element map is properly populated and used by browser tools."""
    logger.info("Starting element map test")
    
    # Initialize browser agent
    async with BrowserAgent(headless=False) as agent:
        # Navigate to a test page with interactive elements
        logger.info("Navigating to test page")
        await navigate("https://example.com")
        
        # Get the element map from the DOM service
        logger.info("Getting element map from DOM service")
        element_map = agent.dom_service.get_element_map()
        logger.info(f"Element map contains {len(element_map)} elements")
        
        # Log the element map contents
        for hash_key, xpath in element_map.items():
            logger.info(f"Element hash: {hash_key}, XPath: {xpath}")
        
        # Test running a simple task that uses the element map
        logger.info("Running a simple task that uses element hashes")
        result = await agent.run("Click on any link on the page")
        logger.info(f"Task result: {result}")
        
        # Wait a moment to see the result
        await asyncio.sleep(2)
    
    logger.info("Element map test completed")

if __name__ == "__main__":
    asyncio.run(test_element_map())
