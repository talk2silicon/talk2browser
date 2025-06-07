"""
Example demonstrating the DOM service for interactive element detection and highlighting.
"""
import asyncio
import logging
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from playwright.async_api import async_playwright
from src.talk2browser.browser.dom.service import DOMService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Main function to demonstrate the DOM service."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Navigating to https://github.com...")
        await page.goto("https://github.com", wait_until="domcontentloaded")
        
        service = DOMService(page)
        
        print("Finding interactive elements...")
        result = await service.get_dom_tree(highlight_elements=True)
        
        if 'error' in result:
            print(f"Error: {result['error']}")
            return
            
        print("\nInteractive elements found:")
        for element_id, element in result['map'].items():
            if element.get('isInteractive'):
                print(f"- {element.get('tagName', 'unknown')} at {element.get('xpath', 'unknown')}")
        
        # Wait a bit to see the highlights
        await asyncio.sleep(5)
        
        # Find a specific element by description
        description = "more information"
        print(f"\nSearching for element matching: '{description}'")
        element = await service.find_best_match(description)
        
        if element:
            print(f"\nFound element: {element.tag_name} - {element.text}")
            print(f"XPath: {element.xpath}")
            
            # Click on the element if it's clickable
            if element.is_interactive:
                print(f"Clicking on the element...")
                await service.click_element(element)
                await asyncio.sleep(2)  # Wait for navigation
        else:
            print("No matching element found")
        
        await service.clear_highlights()
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
