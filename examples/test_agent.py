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
    "uc": (
        "Go to https://www.canberra.edu.au/. "
        "Find resources for International students. "
        "Select undergraduate, Bachelor of Information Technology (322AA.8). "
        "Extract and create a PDF of the admission requirements for this course."
        "create playwright script for these actions."
    ),
    "uc2": (
        "Go to https://www.canberra.edu.au/. "
        "Find resources for International students. fill the form with Kamal as first name, Perera as last name, kamal@abc.com as email, australia as country and press next button"
        "Download the course guide"
    ),
    "eat": (
    "Go to https://www.ubereats.com/au. "
    "Set the delivery address as 65 Stowport Avenue, Crace. "
    "After entering the address, wait for the delivery time dropdown to appear. "
    "Select 'Deliver now' from the dropdown (do not proceed until it is selected). "
    "Click the 'Find Food' button to proceed. "
    "After clicking 'Find Food', wait for the restaurant list/results to appear. If the restaurant list does not appear within a reasonable time, log all visible interactive elements and their hashes for debugging and stop. "
    "Only attempt to click a hash that is present in the current list of interactive elements. "
    "Search for the 'KFC' restaurant NEAR 65 Stowport Avenue, Crace (Canberra). If multiple KFCs are shown, select the one closest to the delivery address. "
    "If KFC is not found, log all visible restaurant options and their hashes, then stop with an error. "
    "Once on the KFC menu page for your area, add the 'Zinger® Burger Box Hot & Crispy' to the cart (it's $16.45, 4303 kJ). "
    "If the item is not found or unavailable, log an error and stop. "
    "Go to the checkout page. "
    "The box includes: Zinger Burger, 2 pieces of Hot & Crispy™ Boneless, chippies, regular Potato & Gravy, and a drink."
    ),
    "cit": "Go to https://cit.edu.au/ and search for Automotive Electrical Technology course and its Related Courses into a pdf",
    "selenium": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, add Sauce Labs Backpack to the cart, and generate a Selenium script for these actions.",
    "cypress": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, add Sauce Labs Backpack to the cart, and generate a Cypress script for these actions.",
    "playwright": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, and generate a Playwright script for these actions.",
    "playwright_ts": "Navigate to https://www.saucedemo.com, login with ${company_username}/${company_password}, and generate a Playwright TypeScript script for these actions.",
    "filedata": "Navigate to https://www.saucedemo.com and login using the test data in ./data/login_data.json",
    "replay": "replay ./generated/merged_actions_navigate.json",
    "booking": "Find and book a hotel in Paris with suitable accommodations for a family of four (two adults and two children) offering free cancellation for the dates of February 14-21, 2025. on https://www.booking.com/",
    "tiktok": "Go to this tiktok video url, open it and extract the @username from the resulting url. Then do a websearch for this username to find all his social media profiles. Return me the links to the social media profiles with the platform name. https://www.tiktokv.com/share/video/7470981717659110678/, finally create a nice looking pdf with the social media profiles.",
    "dict": "Navigate to https://www.saucedemo.com and login with ${company_username}/${company_password} and then add to cart and checkout",
    "airbnb": (
        "Go to https://www.airbnb.com.au/. "
        "Search for 'Batemans Bay' as the location. "
        "Set the check-in date to July 5th, 2025 and check-out date to July 7th, 2025. "
        "Set the number of guests to 2. "
        "Wait for the search results to load. "
        "Find the listing named 'Garden Bay Beach Getaway - \"The Beach Shack\"'. "
        "Open the listing page. "
        "Extract all available details (title, price, description, amenities, etc.) from the listing. "
        "Create a PDF file with the details of this listing. "
        "If the listing is not found, log all visible listing options and their hashes, then stop with an error."
    ),
    "captcha": "Go to https://captcha.com/demos/features/captcha-demo.aspx and solve the captcha",
    "coder": "Go to https://www.programiz.com/python-programming/online-compiler/ and write a simple calculator program in the online code editor. Then execute the code and suggest improvements if there are any errors.",
    "nrma": (
        "Go to https://www.nrma.com.au/. "
        "Find comprehensive car insurance. "
        "Apply for a quote."
    ),
    "huggingface_top10": (
        "Go to https://huggingface.co/models. "
        "Sort the models by number of downloads. "
        "Create a PDF file with the top 10 models (name, downloads, link)."
    ),
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
