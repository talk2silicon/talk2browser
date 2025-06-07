#!/usr/bin/env python3
"""Simple example of using talk2browser for navigation."""
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from talk2browser.agent import BrowserAgent
from talk2browser.browser import PlaywrightClient
from talk2browser.utils.logging import setup_logging, get_logger

# Set up logging
setup_logging(level=logging.DEBUG)
logger = get_logger(__name__)

# Configure Playwright logger
playwright_logger = logging.getLogger('playwright')
playwright_logger.setLevel(logging.INFO)  # Reduce verbosity of Playwright logs

# Configure httpx logger (used by LangChain)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Configure root logger to show all debug messages
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

async def main():
    """Run the browser agent with a simple navigation task."""
    # Load environment variables from .env file
    load_dotenv()
    
    logger.info("Starting browser agent...")
    logger.debug(f"Environment variables loaded: {'ANTHROPIC_API_KEY' in os.environ}")
    
    # Create the agent
    agent = BrowserAgent(headless=False)
    logger.info("Browser agent created")
    
    try:
        # Simple navigation example
        print("Navigating to example.com...")
        response = await agent.run("Go to example.com and take a screenshot")
        print("\nAgent response:")
        print(response)
        
        # Keep the browser open for a while to see the result
        print("\nBrowser will close in 5 seconds...")
        await asyncio.sleep(5)
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
