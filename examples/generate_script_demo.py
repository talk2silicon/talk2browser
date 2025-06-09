#!/usr/bin/env python3
"""
Demo of generating a Playwright script from recorded browser actions.

This example shows how to use the BrowserAgent to record actions and generate
a Playwright script that can be run independently.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# Import the BrowserAgent
from talk2browser.agent.agent import BrowserAgent

# Load environment variables from .env file
load_dotenv()

async def main():
    """Run the demo and generate a Playwright script."""
    # Initialize the LLM (using Claude 3 Opus)
    llm = ChatAnthropic(
        model="claude-3-opus-20240229",
        temperature=0.1,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Define the output script path
    script_path = "generated_playwright_script.py"
    
    print(f"Starting browser automation demo...")
    print(f"A Playwright script will be generated at: {script_path}")
    print("-" * 50)
    
    # Initialize the browser agent
    async with BrowserAgent(llm=llm, headless=False) as agent:
        # Task 1: Navigate to a website and interact with it
        print("\nTask 1: Navigating to example.com and interacting with the page")
        await agent.run("""
        Go to https://example.com
        Take a screenshot of the page
        Click on any link on the page
        Wait for navigation to complete
        """, output_script=None)  # Don't generate script yet
        
        # Task 2: Search for something on Google
        print("\nTask 2: Searching on Google")
        await agent.run("""
        Go to https://www.google.com
        Find the search box and type 'Playwright Python'
        Press Enter to search
        Wait for the search results to load
        """, output_script=None)
        
        # Task 3: Generate the final script with all recorded actions
        print("\nGenerating Playwright script...")
        await agent.run("""
        Generate a Playwright script with all the actions performed so far
        """, output_script=script_path)
        
        print("\n" + "="*50)
        print(f"✅ Successfully generated Playwright script: {script_path}")
        print("You can now run this script independently with: python", script_path)
        print("="*50)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
