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

import argparse

TASKS = {
    "filedata": "Navigate to https://www.saucedemo.com and login using the test data in ./data/login_data.json",
    "replay": "replay ./generated/merged_actions_navigate.json",
    "booking": "Find and book a hotel in Paris with suitable accommodations for a family of four (two adults and two children) offering free cancellation for the dates of February 14-21, 2025. on https://www.booking.com/",
    "tiktok": "Go to this tiktok video url, open it and extract the @username from the resulting url. Then do a websearch for this username to find all his social media profiles. Return me the links to the social media profiles with the platform name. https://www.tiktokv.com/share/video/7470981717659110678/",
    "dict": "Navigate to https://www.saucedemo.com and login with ${company_username}/${company_password} and then buy Sauce Labs Backpack",
    "captcha": "Go to https://captcha.com/demos/features/captcha-demo.aspx and solve the captcha",
    "coder": "Go to https://www.programiz.com/python-programming/online-compiler/ and write a simple calculator program in the online code editor. Then execute the code and suggest improvements if there are any errors."
}

def get_selected_task():
    parser = argparse.ArgumentParser()
    # Default task is filedata to demonstrate file-based test data loading
    parser.add_argument("--task", choices=TASKS.keys(), default="filedata", help="Task to run (default: filedata)")
    args = parser.parse_args()
    return TASKS[args.task].strip()

async def main():
    """Test the BrowserAgent with a Sauce Demo login flow."""
    # Configure more detailed logging
    logging.getLogger("talk2browser").setLevel(logging.INFO)
    
    # Check for required API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    task = get_selected_task()
    task_name = task.split()[0]
    print(f"[test_agent.py] Running task: {task}")

    try:
        # Create and run the agent
        async with BrowserAgent(headless=False) as agent:
            if task_name == "dict":
                # Configure sensitive data for this task
                sensitive_data = {
                    "company_username": "standard_user",
                    "company_password": "secret_sauce"
                }
                SensitiveDataService.configure(sensitive_data)
                svc = getattr(SensitiveDataService, "_instance", None)
                if svc is None:
                    print("[test_agent.py] SensitiveDataService._instance is None!")
                else:
                    print(f"[test_agent.py] After configure: id={id(svc)} keys={list(getattr(svc, '_secrets', {}).keys())}")
            response = await agent.run(task)
            print("\nAgent response:")
            print(response)
            print("="*80)
            print("TEST COMPLETED!")
            print("="*80)
    except Exception as e:
        print(f"\nError during test execution: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
