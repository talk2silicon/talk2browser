import asyncio
from playwright.async_api import async_playwright, Page, Browser

async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=False)
        page: Page = await browser.new_page()

        # Navigate to the Sauce Demo website
        await page.goto('https://www.saucedemo.com')
        await asyncio.sleep(0.5)

        # Close the browser
        await browser.close()

asyncio.run(main())
