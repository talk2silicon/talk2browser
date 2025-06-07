"""
Test script for DOM element extraction and interaction.
"""
import asyncio
import logging
from playwright.async_api import async_playwright
from talk2browser.browser.dom.service import DOMService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
    """Test DOM element extraction and interaction."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        dom_service = DOMService(page)
        
        # Navigate to a test page
        logger.info("Navigating to GitHub...")
        await page.goto("https://github.com", wait_until="domcontentloaded")
        
        # Get interactive elements
        logger.info("Finding interactive elements...")
        elements = await dom_service.get_interactive_elements(highlight=True)
        logger.info("Found %d interactive elements", len(elements))
        
        # Show first 5 elements with their hashes
        print("\nFirst 5 interactive elements:")
        for i, elem in enumerate(elements[:5], 1):
            print(f"{i}. {elem.tag_name.upper()} - {elem.text or ''}")
            print(f"   Hash: {elem.element_hash}")
            if elem.attributes:
                print(f"   Attrs: {', '.join(f'{k}={v}' for k, v in elem.attributes.items() if k in ['id', 'class', 'name'])}")
            print()
        
        # Print all element texts for debugging
        print("\nAll element texts:")
        for elem in elements:
            print(f"{elem.tag_name}: '{elem.text}'")
            
        # Click the signup button
        signup_elem = next((elem for elem in elements if elem.text and 'Sign up' in elem.text), None)
        if signup_elem:
            print(f"\nClicking signup button: {signup_elem.tag_name} - {signup_elem.text}")
            logger.debug(f"Element map size before click: {len(dom_service._element_map)}")
            logger.debug(f"Element map contents: {[e.tag_name for e in dom_service._element_map.values()]}")
            await dom_service.click_element_by_hash(signup_elem.element_hash)
            await asyncio.sleep(5)  # Wait longer to see the click effect
        else:
            print("\nCould not find signup button")
        
        # Example of how this would be used with LangGraph:
        # 1. Get elements and their hashes
        # 2. Pass element data to LLM with a prompt like "Click on the search box"
        # 3. LLM returns the hash of the element to interact with
        # 4. Use click_element_by_hash(hash) to perform the action
        
        await asyncio.sleep(5)  # Keep browser open longer
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
