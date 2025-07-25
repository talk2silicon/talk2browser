# 🧠 talk2browser – Automate Any Website via Natural Language (Powered by LangGraph)

Ever wanted to automate real browser actions just by **describing** what you want? Meet **talk2browser**, a LangGraph-powered agent that turns prompts into real-time web actions and reusable test scripts.

Hi everyone! 👋 I'm excited to share **talk2browser**, which leverages LangGraph's agent orchestration capabilities to create a self-improving browser automation system. Inspired by the [Browser-Use](https://github.com/browser-use/browser-use) open source project, it takes natural language tasks and executes real browser actions while generating reusable test scripts.

## 🔗 LangGraph Implementation

**talk2browser** showcases advanced LangGraph patterns:

- **Agent State Management** — Complex browser workflows with conditional transitions using `AgentState` TypedDict
- **Dynamic Tool Registration** — 25+ browser automation tools automatically registered as LangGraph tools via decorators
- **Multi-Step Orchestration** — Planning → Execution → Script Generation phases with state persistence
- **Self-Improving Workflows** — Action recording and replay capabilities for iterative improvement
- **Vision Integration** — YOLOv11-based UI element detection with LLM context injection
- **Sensitive Data Handling** — Secure credential management with environment variable injection

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🗣️ **Natural Language Control** | Plain English commands for web app testing and automation |
| 📝 **Multi-Framework Scripts** | Auto-generates Playwright, Cypress, and Selenium code from recorded actions |
| 👁️ **Vision Integration** | YOLOv11-based UI element detection with bounding box coordinates |
| 🔐 **Secure Data Handling** | Environment-based credential management with SecretStr support |
| 📊 **PDF Report Generation** | Comprehensive documentation output with screenshots and structured data |
| ♻️ **Repeatable Execution** | JSON action recording for consistent replay across unlimited runs |
| 🎯 **Element Detection** | Smart CSS/XPath selector resolution with hash-based element mapping |
| 🔧 **Quality Assurance** | Full mypy, flake8, black compliance with automated CI/CD pipeline |

## 🧠 Agent Architecture

The LangGraph agent uses a two-node graph with conditional routing:

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    next: str  # For LangGraph routing
    element_map: Dict[str, str]  # Element hash to xpath mapping
    vision: dict  # Optional vision metadata for LLM context

# Agent workflow: chatbot -> tools -> chatbot (or END)
graph = StateGraph(AgentState)
graph.add_node("agent", self._chatbot)
graph.add_node("tools", ToolNode(TOOLS))
graph.add_conditional_edges("agent", self._route_tools)
```

The agent maintains context across browser sessions and learns from previous automation patterns through the `ActionService` which records all tool calls with execution time, arguments, results, and errors.

> **Note**: The system includes 25+ registered tools including navigation, clicking, form filling, screenshot capture, PDF generation, and script creation capabilities.

## 🚀 Quick Example

Here's how to automate GitHub trending analysis:

```python
import asyncio
from talk2browser.agent.agent import BrowserAgent

async def main():
    # Prepare a test scenario
    task = """Go to https://github.com/trending.
    Extract information about the top 10 trending repositories including:
    - Repository name, owner, description, language, stars, forks, URL
    Create a comprehensive PDF report and generate a Playwright script."""
    
    async with BrowserAgent(headless=False, info_mode=True) as agent:
        response = await agent.run(task)
        print("Agent response:", response)

asyncio.run(main())
```

### CLI Usage

Or use the CLI with predefined tasks:

```bash
python examples/test_agent.py --task github_trending

# Available tasks:
# github_trending, selenium, cypress, playwright, tiktok_trending
```

## 🎮 Getting Started

### Prerequisites
- **Python 3.10+** (required for modern type hints)
- **Git** (for cloning the repository)
- **Anthropic API Key** (for Claude LLM functionality)

### Installation

```bash
git clone https://github.com/talk2silicon/talk2browser
cd talk2browser

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e .[dev]

# Install Playwright browsers
playwright install

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Quick Test

```bash
python examples/test_agent.py --task github_trending
```

## 🔍 Code Quality & Development

This project maintains high code quality through automated checks:

- **🧹 Code Linting** (flake8) - Style and syntax checking
- **🎨 Code Formatting** (black) - Consistent code formatting  
- **🔍 Type Checking** (mypy) - Static type analysis with zero errors
- **🧪 Unit Tests** (pytest) - Automated testing

### Local Development

```bash
# Run all quality checks
flake8 src/ tests/
black --check src/ tests/
mypy src/
pytest

# Auto-fix formatting
black src/ tests/
```

## 📚 Resources

- 🌐 **Website**: https://www.talk2browser.com
- 📂 **GitHub Repository**: https://github.com/talk2silicon/talk2browser  
- 🎥 **Demo Video**: [YouTube Demo](https://www.youtube.com/watch?v=mOcW7bFahdk)
- 📜 **License**: [MIT](https://github.com/talk2silicon/talk2browser/blob/main/LICENSE)


## 🛠️ Technical Architecture

### Core Components

```
talk2browser/
├── src/talk2browser/
│   ├── agent/              # LangGraph agent implementation
│   │   ├── agent.py        # Main BrowserAgent class
│   │   └── llm_singleton.py # LLM instance management
│   ├── browser/            # Browser interaction layer
│   │   ├── client.py       # PlaywrightClient wrapper
│   │   ├── page.py         # BrowserPage abstraction
│   │   └── page_manager.py # Multi-page session management
│   ├── services/           # Core services
│   │   ├── action_service.py      # Action recording/replay
│   │   ├── sensitive_data_service.py # Secure credential handling
│   │   └── vision_service.py      # YOLOv11 integration
│   ├── tools/              # LangGraph tool registry
│   │   ├── browser_tools.py       # 25+ browser automation tools
│   │   ├── script_tools.py        # Script generation tools
│   │   └── file_system_tools.py   # File/PDF operations
│   └── utils/              # Utility functions
├── examples/               # Example scripts and usage
└── tests/                 # Test suite
```

### Tool Registration System

```python
@tool
@resolve_hash_args
async def click(selector: str, *, timeout: int = 5000) -> str:
    """Click on an element matching the CSS selector."""
    # Automatic tool registration with LangGraph
    # Hash-based element resolution
    # Error handling and logging
```

### State Management

```python
# Agent maintains persistent state across tool calls
state = {
    "messages": [HumanMessage, AIMessage, ToolMessage],
    "next": "tools",  # or "agent" or END
    "element_map": {"#abc123": "xpath=//button[@id='submit']"},
    "vision": {"detections": [...], "image_path": "..."}
}
```

## 🤝 Community Questions

I'd love to hear from the LangChain community:

1. **What real-world automation workflows** could benefit from natural language control? (e.g., E2E testing, data extraction, monitoring)
2. **How do you currently approach** multi-step browser automation with state persistence across actions?
3. **What LangGraph patterns** have you found most effective for conditional routing and error recovery in agent workflows?
4. **How do you handle** dynamic web content and element detection in your automation projects?
5. **What's your experience** with integrating computer vision (YOLO, OCR) into LangChain/LangGraph workflows?
6. **How do you manage** sensitive data and credentials in production automation systems?
7. **What testing frameworks** would you most want to see supported for script generation?

## ⚠️ What to Watch Out For

- **Vision/YOLOv11 Integration:** Optional feature. Requires a YOLOv11 model file and additional setup. Not required for core browser automation.
- **Script Summarization:** (Planned) Feature for AI-powered summaries of generated automation scripts is on the roadmap but not yet implemented.
- **PDF Generation:** Fully supported. Generates comprehensive PDF reports with execution details and screenshots.
- **Manual Action Override:** Partially implemented. Human-in-the-loop/manual override is available for some actions and is being actively enhanced for broader coverage.

## 🔮 Future Roadmap

- **PDF Script Documentation** — Generate comprehensive PDF reports for generated test scripts with execution details and screenshots
- **Script Summarization** — AI-powered summaries of generated automation scripts with key actions and validation points
- **Enhanced Manual Action Override** — Improved human-in-the-loop capabilities for manual intervention during automation
- **Performance Optimization** — Faster element detection and action execution
- **Error Handling** — Better recovery from browser automation failures
- **Test Coverage** — Expanded unit and integration test suite

## 🛠️ Technical Stack

- **LangGraph**: Agent orchestration and state management
- **Playwright**: Browser automation engine with 25+ registered tools
- **Claude 3 Opus/Haiku**: Natural language reasoning and planning
- **YOLOv11**: Computer vision for UI element detection
- **Python 3.10+**: Core implementation with full type safety
- **Pydantic**: Data validation and settings management

---

**Looking for feedback, use cases, and contributions!** What browser automation challenges could this help solve for your projects? 🤔

*Feel free to star ⭐ the repo if you find this interesting!*

## 🏷️ Tags
`#langgraph` `#browser-automation` `#playwright` `#ai-agents` `#test-automation` `#natural-language` `#python` `#claude` `#computer-vision` `#pdf-generation`
