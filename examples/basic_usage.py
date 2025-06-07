#!/usr/bin/env python3
"""Basic usage example for talk2browser."""
import asyncio
from talk2browser.agent import BrowserAgent


async def main():
    """Run a simple browser automation."""
    async with BrowserAgent(headless=False) as agent:
        result = await agent.run("Navigate to example.com")
        print("Execution result:", result)


if __name__ == "__main__":
    asyncio.run(main())
