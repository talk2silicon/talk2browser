"""Test script for the BrowserAgent with Sauce Demo login example."""
import asyncio
import logging
import os
from dotenv import load_dotenv

from talk2browser.utils.logging import setup_logging
from talk2browser.agent.agent import BrowserAgent
from talk2browser.services.sensitive_data_service import SensitiveDataService  # <-- Added import

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

TASK2 = """
Go to this tiktok video url, open it and extract the @username from the resulting url. Then do a websearch for this username to find all his social media profiles. Return me the links to the social media profiles with the platform name.
https://www.tiktokv.com/share/video/7470981717659110678/ 
"""

TASK3 = """
 replay ./generated/merged_actions_go.json
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
            # --- ENV VAR secret injection example ---
            print("\n" + "="*80)
            print("TEST 1: ENV VAR SECRET INJECTION")
            print("="*80)
            env_prompt = "Navigate to https://www.saucedemo.com and login with ${SAUCE_USER}/${SAUCE_PASS} and then buy Sauce Labs Backpack"
            response_env = await agent.run(env_prompt)
            print("\nAgent response (env vars):")
            print(response_env)
            print("="*80)

            # --- sensitive_data dict injection example ---
            print("\n" + "="*80)
            print("TEST 2: sensitive_data DICT INJECTION")
            print("="*80)
            sensitive_data = {
                "company_username": "standard_user",
                "company_password": "secret_sauce"
            }
            # IMPORTANT: Use ${...} placeholders so the LLM/tool layer will pass these to the resolver!
            SensitiveDataService.configure(sensitive_data)
            # Debug log from test script
            svc = getattr(SensitiveDataService, "_instance", None)
            if svc is None:
                print("[test_agent.py] SensitiveDataService._instance is None!")
            else:
                print(f"[test_agent.py] After configure: id={id(svc)} keys={list(getattr(svc, '_secrets', {}).keys())}")
            dict_prompt = "Navigate to https://www.saucedemo.com and login with ${company_username}/${company_password} and then buy Sauce Labs Backpack"
            logging.debug("Running dict_prompt: %s", dict_prompt)
            #response_dict = await agent.run(dict_prompt)
            print("\nAgent response (sensitive_data dict):")
            print(response_dict)
            print("="*80)

            print("SAUCE DEMO LOGIN TEST COMPLETED!")
            print("="*80)
            
    except Exception as e:
        print(f"\nError during test execution: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
