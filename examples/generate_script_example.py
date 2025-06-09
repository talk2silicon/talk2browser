#!/usr/bin/env python3
"""Example of generating a Playwright script from agent actions."""
import asyncio
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from talk2browser.agent.agent import BrowserAgent

# Load environment variables
load_dotenv()

async def main():
    # Initialize the LLM
    llm = ChatAnthropic(
        model="claude-3-opus-20240229",
        temperature=0.1,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Initialize the agent
    async with BrowserAgent(llm=llm, headless=False) as agent:
        # Run a task and generate a script
        await agent.run(
            "Navigate to https://example.com and search for 'Playwright'",
            output_script="example_script.py"
        )
        
        # You can also generate a script after running multiple tasks
        # await agent.run("Click on the first search result")
        # script_path = await agent.tool_registry.generate_playwright_script("search_results_script.py")
        # print(f"Generated script at: {script_path}")

if __name__ == "__main__":
    asyncio.run(main())
