from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to the login page
        await page.goto('https://www.saucedemo.com')
        await asyncio.sleep(0.5)

        # Fill in the username
        await page.fill('#user-name', 'standard_user')
        await asyncio.sleep(0.5)

        # Fill in the password
        await page.fill('#password', 'secret_sauce')
        await asyncio.sleep(0.5)

        # Click the login button
        await page.click('#login-button')
        await asyncio.sleep(0.5)

        # Close the browser
        await browser.close()

asyncio.run(main())
