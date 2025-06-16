"""Test script for the BrowserAgent with Sauce Demo login example."""
import asyncio
import logging
import os
from dotenv import load_dotenv

from talk2browser.utils.logging import setup_logging
from talk2browser.agent.agent import BrowserAgent

# Load environment variables from .env
load_dotenv()

# Set up logging from LOG_LEVEL in .env
level_str = os.getenv("LOG_LEVEL", "INFO").upper()
level = getattr(logging, level_str, logging.INFO)
setup_logging(level=level)

# Suppress noisy DEBUG logs from external libraries unless LOG_LEVEL is DEBUG
if level > logging.DEBUG:
    logging.getLogger("anthropic").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.INFO)

TASK = """
Find and book a hotel in Paris with suitable accommodations for a family of four (two adults and two children) offering free cancellation for the dates of February 14-21, 2025. on https://www.booking.com/
"""

async def main():
    """Test the BrowserAgent with a Sauce Demo login flow."""
    # Configure more detailed logging
    logging.getLogger("talk2browser").setLevel(logging.INFO)
    
    # Check for required API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    try:
        # Create and run the agent
        async with BrowserAgent(headless=False) as agent:
            # Step 1: Navigate to Sauce Demo
            print("\n" + "="*80)
            print("STEP 1: Navigate to Sauce Demo")
            print("="*80)
            # response = await agent.run(
            #     "Navigate to the Sauce Demo website at https://www.saucedemo.com and login with standard_user/secret_sauce and then buy Sauce Labs Backpack"
            # )

            # response = await agent.run(
            #     "Navigate to the https://browser.windsurf.com and create a selenium script"
            # )

            response = await agent.run(
                "read and replay the action json file in ./generated/actions_read.json"
            )


            # response = await agent.run(
            #     TASK
            # )
 
            print("\nAgent response:")
            print(response)
            
            print("SAUCE DEMO LOGIN TEST COMPLETED!")
            print("="*80)
            
    except Exception as e:
        print(f"\nError during test execution: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
