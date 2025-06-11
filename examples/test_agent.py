"""Test script for the BrowserAgent with Sauce Demo login example."""
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from talk2browser.agent.agent import BrowserAgent

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
            response = await agent.run(
                "Navigate to the Sauce Demo website at https://www.saucedemo.com and login with standard_user/secret_sauce and then buy Sauce Labs Backpack"
            )
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
