"""Test script for the BrowserAgent."""
import asyncio
import logging
import os
from dotenv import load_dotenv

from talk2browser.agent.agent import BrowserAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def main():
    """Test the BrowserAgent with a simple task."""
    # Load environment variables
    load_dotenv()
    
    # Create and run the agent
    async with BrowserAgent(headless=False) as agent:
        # Test direct navigation to a specific search result
        response = await agent.run("Go to the LangGraph GitHub repository at https://github.com/langchain-ai/langgraph")
        print("\nAgent response:")
        print(response)

if __name__ == "__main__":
    asyncio.run(main())
