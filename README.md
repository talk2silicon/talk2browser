# Talk2Browser

A natural language browser automation tool powered by LLMs and Playwright, inspired by the talk2n8n architecture.

## 🚀 Features

- **Natural Language Control**: Control your browser using simple English instructions
- **Dynamic Tool Discovery**: Automatically discovers and exposes Playwright methods as tools
- **LLM-Powered**: Uses Claude 3 Opus for intelligent tool selection and execution
- **Playwright Integration**: Full access to Playwright's powerful browser automation capabilities
- **LangGraph Workflows**: Flexible workflow orchestration with LangGraph
- **Script Generation**: Automatically generate Playwright scripts from agent actions

## 🛠️ Installation

1. Install Python 3.10 or higher
2. Install Playwright browsers:
   ```bash
   playwright install
   ```
3. Install the package in development mode:
   ```bash
   pip install -e .[dev]
   ```
4. Copy `.env.example` to `.env` and add your Anthropic API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

## 🎬 Playwright Script Generation

Automatically generate Playwright scripts from agent actions:

```python
import asyncio
from langchain_anthropic import ChatAnthropic
from talk2browser.agent.agent import BrowserAgent

async def main():
    # Initialize LLM
    llm = ChatAnthropic(model="claude-3-opus-20240229")
    
    # Run agent and generate script
    async with BrowserAgent(llm=llm, headless=False) as agent:
        await agent.run(
            "Navigate to example.com and search for 'Playwright'",
            output_script="example_script.py"
        )

asyncio.run(main())
```

### Advanced Usage

Generate a script after multiple actions:

```python
async with BrowserAgent(llm=llm) as agent:
    await agent.run("Go to example.com")
    await agent.run("Click on the search box")
    
    # Generate script of all recorded actions
    script_path = await agent.tool_registry.generate_playwright_script("my_script.py")
    print(f"Generated script: {script_path}")
```

### Standalone Script Generator

Convert recorded actions to a Playwright script:

```bash
python -m talk2browser.scripts.generate_playwright_script recorded_actions.json -o output_script.py
```

## 🚀 Quick Start

```python
import asyncio
from dotenv import load_dotenv
from talk2browser.agent import BrowserAgent

async def main():
    # Load environment variables
    load_dotenv()
    
    # Create and run the browser agent
    agent = BrowserAgent(headless=False)
    try:
        # Run a natural language command
        response = await agent.run("Go to example.com and take a screenshot")
        print("Agent response:", response)
    finally:
        # Clean up
        if hasattr(agent, 'graph'):
            del agent.graph

if __name__ == "__main__":
    asyncio.run(main())
```

## 🤖 How It Works

1. **Tool Registration**: Playwright's Page and ElementHandle methods are automatically registered as tools
2. **LLM Tool Selection**: The agent uses Claude 3 Opus to select the appropriate tool based on the user's request
3. **Tool Execution**: The selected tool is executed with the provided arguments
4. **Response Generation**: The agent generates a response based on the tool's output

## 📁 Project Structure

```
talk2browser/
├── src/
│   └── talk2browser/
│       ├── browser/       # Browser interaction and client
│       ├── tools/         # Tool registry and dynamic tool discovery
│       ├── agent/         # LangGraph agent implementation
│       └── utils/         # Utility functions and logging
├── examples/              # Example scripts
├── tests/                 # Test suite
├── .env.example          # Example environment variables
└── README.md             # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📧 Contact

Your Name - your.email@example.com

Project Link: [https://github.com/yourusername/talk2browser](https://github.com/yourusername/talk2browser)
