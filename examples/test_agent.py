"""Test script for the BrowserAgent with Sauce Demo login example."""
import asyncio
import logging
import os
from dotenv import load_dotenv

from talk2browser.utils.logging import setup_logging
import pathlib

# Ensure logs directory exists
def ensure_log_dir():
    log_dir = pathlib.Path('logs')
    log_dir.mkdir(exist_ok=True)
    return log_dir / 'agent.log'

from talk2browser.agent.agent import BrowserAgent
from talk2browser.services.sensitive_data_service import SensitiveDataService  # <-- Added import

# Load environment variables from .env
load_dotenv()

# Set up logging from LOG_LEVEL in .env
level_str = os.getenv("LOG_LEVEL", "INFO").upper()
level = getattr(logging, level_str, logging.INFO)
log_file = ensure_log_dir()
setup_logging(level=level, log_file=str(log_file))
print(f"[test_agent.py] Logging to file: {log_file}")

# Suppress noisy DEBUG logs from external libraries unless LOG_LEVEL is DEBUG
if level > logging.DEBUG:
    logging.getLogger("anthropic").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.INFO)

import argparse

TASKS = {
    "selenium": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, add Sauce Labs Backpack to the cart, and generate a Selenium script for these actions.",
    "cypress": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, add Sauce Labs Backpack to the cart, and generate a Cypress script for these actions.",
    "playwright": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, and generate a Playwright script for these actions.",
    "playwright_ts": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, and generate a Playwright TypeScript script for these actions.",
    "filedata": "Navigate to https://www.saucedemo.com and login using the test data in ./data/login_data.json",
    "github_trending": (
        "Go to https://github.com/trending. "
        "Extract information about the top 10 trending repositories including: "
        "- Repository name "
        "- Owner/organization "
        "- Description "
        "- Primary programming language "
        "- Number of stars "
        "- Number of forks "
        "- URL to the repository "
        "Create a comprehensive PDF report with all the extracted information, formatted in a clean and readable way."
        "Finally generate a Playwright python script that automates this entire process."
    ),
    "tiktok_trending": (
        "Go to https://www.tiktok.com/channel/trending-now?lang=en. "
        "Wait for the trending videos to load. "
        "find the video with most views and click on it. "
        "Wait for the video to load. "
        "Find the like count and print it. "
        "Generate a Playwright python script that automates this entire process."
    ),
    "amazon_bose": (
        "Go to https://www.amazon.com.au. "
        "Search for 'Bose Smart Ultra Soundbar'. "
        "Order by review count. "
        "Extract information about all available options including: "
        "- Product name "
        "- Price "
        "- Seller/retailer name "
        "- Rating (if available) "
        "- Delivery options (if available) "
        "Create a comprehensive PDF report with all the extracted information, "
        "formatted in a clean and readable way with proper headings and sections."
    ),
    "gumtree_dogs": (
        "Go to https://www.gumtree.com.au/. "
        "Search for 'cocker spaniel' dogs in the Canberra ACT region. "
        "Sort the results by most recent. "
        "Extract information about the top 10 listings including: "
        "- Title of the listing "
        "- Price "
        "- Location "
        "- Date posted "
        "- Description (if available) "
        "- Seller information (if available) "
        "Create a comprehensive PDF report with all the extracted information, formatted in a clean and readable way."
        "Finally generate a Playwright python script that automates this entire process."
    )
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
            sensitive_data = {
                "company_username": os.getenv("COMPANY_USERNAME", "standard_user"),
                "company_password": os.getenv("COMPANY_PASSWORD", "secret_sauce")
            }
            print(f"[test_agent.py] Injecting sensitive_data keys: {list(sensitive_data.keys())}")
            response = await agent.run(task, sensitive_data=sensitive_data)
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
