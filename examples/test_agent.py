"""Test script for the BrowserAgent."""
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
    """Test the BrowserAgent with a multi-step navigation task."""
    # Configure more detailed logging
    logging.getLogger("talk2browser").setLevel(logging.INFO)
    
    # Check for required API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    try:
        # Create and run the agent
        async with BrowserAgent(headless=False) as agent:
            # First level: Navigate to the LangGraph GitHub repository
            print("\n" + "="*80)
            print("STEP 1: Navigate to LangGraph GitHub Repository")
            print("="*80)
            response = await agent.run(
                "Navigate to the LangGraph GitHub repository at https://github.com/langchain-ai/langgraph"
            )
            print("\nAgent response:")
            print(response)
            
            # Add a small delay to ensure page is fully loaded
            await asyncio.sleep(2)
            
            # Second level: Find and click on the Issues tab
            print("\n" + "="*80)
            print("STEP 2: Navigate to Issues Section")
            print("="*80)
            response = await agent.run(
                "Find and click on the 'Issues' tab to view the open issues. "
                "Make sure to wait for the page to fully load after clicking."
            )
            print("\nAgent response:")
            print(response)
            
            # Add a small delay to ensure issues are loaded
            await asyncio.sleep(3)
            
            # Third level: Interact with the issues page
            print("\n" + "="*80)
            print("STEP 3: Analyze First Open Issue")
            print("="*80)
            response = await agent.run(
                "Find the first open issue in the list. Extract and summarize the following:\n"
                "1. Issue title\n"
                "2. Issue number\n"
                "3. First comment or description (first 100 characters)"
            )
            print("\nAgent response:")
            print(response)
            
            # Final status
            print("\n" + "="*80)
            print("MULTI-STEP NAVIGATION TEST COMPLETED SUCCESSFULLY!")
            print("="*80)
            
    except Exception as e:
        print(f"\nError during test execution: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
