from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to the website
        await page.goto('https://www.saucedemo.com')
        await asyncio.sleep(0.5)
        
        try:
            # Click the login button without entering credentials
            await page.locator('#login-button').click()
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Error clicking login button: {str(e)}")
        
        try:
            # Add an item to the cart
            await page.locator('#add-to-cart-sauce-labs-backpack').click()
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Error adding item to cart: {str(e)}")
        
        try:
            # Navigate to the shopping cart page
            await page.locator('.shopping_cart_link').click()
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Error navigating to shopping cart: {str(e)}")
        
        # Close the browser
        await browser.close()

asyncio.run(main())
