from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to the login page
        await page.goto('https://www.saucedemo.com')
        await asyncio.sleep(0.5)

        # Click on the username input field
        await page.locator('xpath=html/body/div/div/div[2]/div[1]/div/div/form/input').click()
        await asyncio.sleep(0.5)

        # Click on the login button without entering credentials
        await page.locator('xpath=html/body/div/div/div/div[2]/div/div/div/div[1]/div[2]/div[2]/button').click()
        await asyncio.sleep(0.5)

        # Click on the shopping cart link
        await page.locator('xpath=html/body/div/div/div/div[1]/div[1]/div[3]/a').click()
        await asyncio.sleep(0.5)

        # Click on the "Continue Shopping" button
        await page.locator('xpath=html/body/div/div/div/div[2]/div/div[2]/button[2]').click()
        await asyncio.sleep(0.5)

        await browser.close()

asyncio.run(main())
