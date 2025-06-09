from playwright.async_api import async_playwright, Page, expect

async def login(page: Page):
    # Navigate to the login page
    await page.goto('https://www.saucedemo.com')

    # Fill in the username
    await page.fill('[data-test="username"]', 'standard_user')

    # Fill in the password
    await page.fill('[data-test="password"]', 'secret_sauce')

    # Click the login button
    await page.click('[data-test="login-button"]')

    # Wait for the page to load after login
    await page.wait_for_load_state('networkidle')

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await login(page)
            # Add further actions or assertions here
        except Exception as e:
            print(f'An error occurred: {e}')
        finally:
            await browser.close()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
