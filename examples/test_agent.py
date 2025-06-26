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
    "cit": "Go to https://cit.edu.au/ and search for Automotive Electrical Technology course and create a pdf with entry requirements.",
    "selenium": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, add Sauce Labs Backpack to the cart, and generate a Selenium script for these actions.",
    "cypress": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, add Sauce Labs Backpack to the cart, and generate a Cypress script for these actions.",
    "playwright": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, and generate a Playwright script for these actions.",
    "filedata": "Navigate to https://www.saucedemo.com and login using the test data in ./data/login_data.json",
    "replay": "replay ./generated/merged_actions_navigate.json",
    "booking": "Find and book a hotel in Paris with suitable accommodations for a family of four (two adults and two children) offering free cancellation for the dates of February 14-21, 2025. on https://www.booking.com/",
    "tiktok": "Go to this tiktok video url, open it and extract the @username from the resulting url. Then do a websearch for this username to find all his social media profiles. Return me the links to the social media profiles with the platform name. https://www.tiktokv.com/share/video/7470981717659110678/",
    "dict": "Navigate to https://www.saucedemo.com and login with ${company_username}/${company_password} and then add to cart and checkout",
    "captcha": "Go to https://captcha.com/demos/features/captcha-demo.aspx and solve the captcha",
    "coder": "Go to https://www.programiz.com/python-programming/online-compiler/ and write a simple calculator program in the online code editor. Then execute the code and suggest improvements if there are any errors.",
    "migros": """
   ### Prompt for Shopping Agent – Migros Online Grocery Order

**Objective:**
Visit [Migros Online](https://www.migros.ch/en), search for the required grocery items, add them to the cart, select an appropriate delivery window, and complete the checkout process using TWINT.

**Important:**
- Make sure that you don't buy more than it's needed for each article.
- After your search, if you click  the "+" button, it adds the item to the basket.
- if you open the basket sidewindow menu, you can close it by clicking the X button on the top right. This will help you navigate easier.
---

### Step 1: Navigate to the Website
- Open [Migros Online](https://www.migros.ch/en).
- You should be logged in as Nikolaos Kaliorakis

---

### Step 2: Add Items to the Basket

#### Shopping List:

**Meat & Dairy:**
- Beef Minced meat (1 kg)
- Gruyère cheese (grated preferably)
- 2 liters full-fat milk
- Butter (cheapest available)

**Vegetables:**
- Carrots (1kg pack)
- Celery
- Leeks (1 piece)
- 1 kg potatoes

At this stage, check the basket on the top right (indicates the price) and check if you bought the right items.

**Fruits:**
- 2 lemons
- Oranges (for snacking)

**Pantry Items:**
- Lasagna sheets
- Tahini
- Tomato paste (below CHF2)
- Black pepper refill (not with the mill)
- 2x 1L Oatly Barista(oat milk)
- 1 pack of eggs (10 egg package)

#### Ingredients I already have (DO NOT purchase):
- Olive oil, garlic, canned tomatoes, dried oregano, bay leaves, salt, chili flakes, flour, nutmeg, cumin.

---

### Step 3: Handling Unavailable Items
- If an item is **out of stock**, find the best alternative.
- Use the following recipe contexts to choose substitutions:
  - **Pasta Bolognese & Lasagna:** Minced meat, tomato paste, lasagna sheets, milk (for béchamel), Gruyère cheese.
  - **Hummus:** Tahini, chickpeas, lemon juice, olive oil.
  - **Chickpea Curry Soup:** Chickpeas, leeks, curry, lemons.
  - **Crispy Slow-Cooked Pork Belly with Vegetables:** Potatoes, butter.
- Example substitutions:
  - If Gruyère cheese is unavailable, select another semi-hard cheese.
  - If Tahini is unavailable, a sesame-based alternative may work.

---

### Step 4: Adjusting for Minimum Order Requirement
- If the total order **is below CHF 99**, add **a liquid soap refill** to reach the minimum. If it;s still you can buy some bread, dark chockolate.
- At this step, check if you have bought MORE items than needed. If the price is more then CHF200, you MUST remove items.
- If an item is not available, choose an alternative.
- if an age verification is needed, remove alcoholic products, we haven't verified yet.

---

### Step 5: Select Delivery Window
- Choose a **delivery window within the current week**. It's ok to pay up to CHF2 for the window selection.
- Preferably select a slot within the workweek.

---

### Step 6: Checkout
- Proceed to checkout.
- Select **TWINT** as the payment method.
- Check out.
- 
- if it's needed the username is: nikoskalio.dev@gmail.com 
- and the password is : TheCircuit.Migros.dev!
---

### Step 7: Confirm Order & Output Summary
- Once the order is placed, output a summary including:
  - **Final list of items purchased** (including any substitutions).
  - **Total cost**.
  - **Chosen delivery time**. """
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
