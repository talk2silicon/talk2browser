import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to the Sauce Demo login page
        await page.goto('https://www.saucedemo.com')
        await asyncio.sleep(0.5)

        await browser.close()

asyncio.run(main())
