#!/usr/bin/env python3
"""
Simple example of generating a Playwright script from browser actions.

This example demonstrates the basic usage of the script generation feature.
"""
import asyncio
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from talk2browser.agent.agent import BrowserAgent

async def main():
    """Run a simple browser automation and generate a script."""
    # Load environment variables
    load_dotenv()
    
    # Initialize the LLM
    llm = ChatAnthropic(
        model="claude-3-opus-20240229",
        temperature=0.1,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Output script path - save in the scripts directory
    script_dir = os.path.join(os.path.dirname(__file__), "..", "src", "talk2browser", "scripts")
    os.makedirs(script_dir, exist_ok=True)
    script_path = os.path.join(script_dir, "generated_playwright_script.py")
    
    print("Starting simple browser automation...")
    print(f"A Playwright script will be generated at: {os.path.abspath(script_path)}")
    
    async with BrowserAgent(llm=llm, headless=False) as agent:
        # Run a simple task and generate the script
        await agent.run(
            "Go to https://www.saucedemo.com and login with standard_user/secret_sauce",
            output_script=script_path
        )
        
        print("\nScript generation complete!")
        print(f"You can now run the generated script with:")
        print(f"cd {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")
        print(f"python -m src.talk2browser.scripts.{os.path.splitext(os.path.basename(script_path))[0]}")

if __name__ == "__main__":
    asyncio.run(main())
