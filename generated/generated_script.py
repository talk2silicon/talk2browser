from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # Navigate to the login page
            await page.goto('https://www.saucedemo.com')
            await asyncio.sleep(0.5)

            # Fill in the username and password
            await page.fill('#user-name', 'standard_user')
            await asyncio.sleep(0.5)
            await page.fill('#password', 'secret_sauce')
            await asyncio.sleep(0.5)

            # Click the login button
            await page.click('#login-button', timeout=10000, force=False)
            await asyncio.sleep(0.5)

            # Wait for the inventory list to be visible
            await page.wait_for_selector('.inventory_list', state='visible', timeout=30000)
            await asyncio.sleep(0.5)

            # Click on a specific item
            await page.click('#item_4_title_link', timeout=10000, force=False)
            await asyncio.sleep(0.5)

            # Click on the shopping cart link
            await page.click('.shopping_cart_link', timeout=10000, force=False)
            await asyncio.sleep(0.5)

            # Click the checkout button
            await page.click('#checkout', timeout=10000, force=False)
            await asyncio.sleep(0.5)

            # Fill in the checkout information
            await page.fill('#first-name', 'John')
            await asyncio.sleep(0.5)
            await page.fill('#last-name', 'Doe')
            await asyncio.sleep(0.5)
            await page.fill('#postal-code', '12345')
            await asyncio.sleep(0.5)

            # Click the continue button
            await page.click('#continue', timeout=10000, force=False)
            await asyncio.sleep(0.5)

            # Click the finish button
            await page.click('#finish', timeout=10000, force=False)
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"An error occurred: {str(e)}")

        finally:
            await browser.close()

asyncio.run(main())
