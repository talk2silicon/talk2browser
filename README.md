# 🧠 talk2browser – Browser automation with everyday Language (Powered by LangGraph)

Ever wanted to automate real browser actions just by **describing** what you want? Meet **talk2browser**, a LangGraph-powered agent that turns prompts into real-time web actions and reusable test scripts.

A self-improving browser automation system powered by LLMs, Playwright, and modular agent services. Generate, record, and replay test scripts using natural language and advanced automation tools.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🗣️ **Natural Language Control** | Plain English commands for web app testing and automation |
| 📝 **Multi-Framework Scripts** | Auto-generates Playwright, Cypress, and Selenium code from recorded actions |
| 👁️ **Vision Integration** | YOLOv11-based UI element detection with bounding box coordinates (optional, requires model file) |
| 🔐 **Secure Data Handling** | Environment-based credential management with SecretStr support |
| 📊 **PDF Report Generation** | Comprehensive documentation output with screenshots and structured data |
| ♻️ **Repeatable Execution** | JSON action recording for consistent replay across unlimited runs |
| 🎯 **Element Detection** | Smart CSS/XPath selector resolution with hash-based element mapping |
| 🔧 **Quality Assurance** | Full mypy, flake8, black compliance with automated CI/CD pipeline |

---

## 🔗 LangGraph Implementation

**talk2browser** showcases advanced LangGraph patterns:

- **Agent State Management** — Complex browser workflows with conditional transitions using `AgentState` TypedDict
- **Dynamic Tool Registration** — 25+ browser automation tools automatically registered as LangGraph tools via decorators
- **Multi-Step Orchestration** — Planning → Execution → Script Generation phases with state persistence
- **Self-Improving Workflows** — Action recording and replay capabilities for iterative improvement
- **Vision Integration** — YOLOv11-based UI element detection with LLM context injection
- **Sensitive Data Handling** — Secure credential management with environment variable injection

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

---

## 🛠️ Installation

### Prerequisites
- **Python 3.10+** (required)
- **Git** (for cloning the repository)
- **Anthropic API Key** (for LLM functionality)

### Step 1: Environment Setup

**Create a virtual environment (recommended):**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Step 2: Clone and Install

```bash
# Clone the repository
git clone https://github.com/talk2silicon/talk2browser.git
cd talk2browser

# Install the package in development mode (includes all dependencies)
pip install -e .[dev]

# Install Playwright browsers (required for browser automation)
python -m playwright install
```

**Note for Contributors:** All dependencies are declared in `pyproject.toml`. The `pip install -e .[dev]` command installs:
- All runtime dependencies (playwright, langchain, etc.)
- All development dependencies (pytest, mypy, black, flake8)
- No additional manual pip installs should be needed

### Step 3: API Key Setup

1. **Get your Anthropic API Key:**
   - Visit [Anthropic Console](https://console.anthropic.com/)
   - Sign up or log in to your account
   - Navigate to "API Keys" section
   - Create a new API key with appropriate permissions
   - Copy the key (starts with `sk-ant-`)

2. **Configure environment variables:**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env file and add your API key
   # Replace YOUR_API_KEY_HERE with your actual key
   ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
   ```

### Step 4: Verify Installation

Test your setup with a simple example:

```bash
# Run the GitHub trending example
python examples/test_agent.py --task github_trending
```

**Expected output:**
- Browser window opens
- Navigates to GitHub trending page
- Extracts repository information
- Generates a PDF report
- Creates a Playwright script

If successful, you'll see files like:
- `trending_now_report.pdf`
- `github_trending_script.py`

---

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

## 🔧 Troubleshooting

### Common Issues

**1. "No module named 'playwright'"**
```bash
# Install Playwright browsers
python -m playwright install
```

**2. "Anthropic API key not found"**
- Check your `.env` file exists and contains `ANTHROPIC_API_KEY`
- Verify the key starts with `sk-ant-`
- Ensure `.env` is in the project root directory

**3. "Browser launch failed"**
```bash
# Reinstall Playwright browsers
python -m playwright install --force
```

**4. "Permission denied" on macOS/Linux**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate
# Try with --user flag if needed
pip install --user -e .[dev]
```

**5. PDF generation fails**
- Ensure you have sufficient disk space
- Check write permissions in the project directory
- Verify Playwright browsers are installed

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/talk2silicon/talk2browser/issues)
- **Discussions**: [GitHub Discussions](https://github.com/talk2silicon/talk2browser/discussions)
- **Website**: [talk2browser.com](http://www.talk2browser.com)

---

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
        # LLM-driven script generation: all steps and script output are requested in natural language
        script_path = await agent.run(
            "Navigate to example.com, search for 'Playwright', and generate a Playwright script for these actions."
        )
        print(f"Generated script: {script_path}")

asyncio.run(main())
```

### Standalone Script Generator

Convert recorded actions to a Playwright script:

```bash
python -m talk2browser.scripts.generate_playwright_script recorded_actions.json -o output_script.py
```

---

## 🧑‍💻 Example: Run the BrowserAgent from CLI

You can run the BrowserAgent directly from the command line using the provided example script. This allows you to automate browser tasks and generate scripts using natural language instructions or pre-defined scenarios.

**Example usage:**

```bash
python examples/test_agent.py --task github_trending
```

This will:
- Launch the BrowserAgent
- Go to GitHub Trending
- Extract information about the top 10 trending repositories
- Generate a comprehensive PDF report
- Generate a Playwright Python script for the process

You can choose from a variety of tasks:

- `github_trending` (extract GitHub trending repos)
- `selenium`, `cypress`, `playwright`, `playwright_ts` (automation script generation)
- `filedata` (uses test data from file)
- `tiktok_trending`, `amazon_bose`, `gumtree_dogs` (real-world web automation examples)

See the `examples/test_agent.py` file for full details and how to add your own tasks.

---

## ⚡ Quick Start

Here's a more realistic example using the BrowserAgent to automate a real-world scenario, similar to the CLI examples:

```python
import asyncio
import os
from dotenv import load_dotenv
from talk2browser.agent import BrowserAgent

async def main():
    # Load environment variables
    load_dotenv()
    
    # Prepare a test scenario (e.g., GitHub Trending extraction)
    task = (
        "Go to https://github.com/trending. "
        "Extract information about the top 10 trending repositories including: "
        "- Repository name\n- Owner/organization\n- Description\n- Primary programming language\n- Number of stars\n- Number of forks\n- URL to the repository. "
        "Create a comprehensive PDF report with all the extracted information, formatted in a clean and readable way. "
        "Finally generate a Playwright python script that automates this entire process."
    )
    
    # Optionally, inject sensitive data if needed
    sensitive_data = {
        "company_username": os.getenv("COMPANY_USERNAME", "standard_user"),
        "company_password": os.getenv("COMPANY_PASSWORD", "secret_sauce")
    }
    
    async with BrowserAgent(headless=False) as agent:
        response = await agent.run(task, sensitive_data=sensitive_data)
        print("Agent response:", response)

if __name__ == "__main__":
    asyncio.run(main())
```

This example will launch the BrowserAgent, navigate to GitHub Trending, extract repository data, generate a PDF report, and produce a Playwright script for the workflow—all driven by natural language.

---

## 🤖 How It Works

1. **Tool Registration**: Playwright's Page and ElementHandle methods are automatically registered as tools
2. **LLM Tool Selection**: The agent uses Claude 3 Opus to select the appropriate tool based on the user's request
3. **Tool Execution**: The selected tool is executed with the provided arguments
4. **Response Generation**: The agent generates a response based on the tool's output

### System Architecture

```mermaid
flowchart TB
    %% Core Flow - Simplified
    User[👤 User] --> |"Natural Language Task"| CLI[🖥️ CLI Interface]
    CLI --> Agent[🤖 AI Agent]
    
    %% AI Processing
    Agent --> |"Analyze Task"| LLM[🧠 LLM Engine]
    LLM --> |"Plan Actions"| Agent
    
    %% Browser Interaction
    Agent --> |"Execute Actions"| Browser[🌐 Browser]
    Browser --> |"Capture Actions"| Recorder[📝 Action Recorder]
    
    %% Script Generation
    Recorder --> |"Action Sequence"| Generator[⚡ Script Generator]
    Generator --> Scripts[📄 Clean Scripts]
    
    %% Output Options
    Scripts --> Selenium[🔧 Selenium]
    Scripts --> Playwright[🎭 Playwright]
    Scripts --> Cypress[🌲 Cypress]
    
    %% Backend Support
    LLM -.-> Claude[Anthropic Claude]
    
    %% Enhanced Features (Secondary)
    Browser -.-> Vision[👁️ Vision Detection]
    Vision -.-> Recorder
    
    %% Clean Styling
    classDef primary fill:#2563eb,stroke:#1e40af,stroke-width:2px,color:#fff
    classDef secondary fill:#059669,stroke:#047857,stroke-width:2px,color:#fff
    classDef tertiary fill:#7c3aed,stroke:#6d28d9,stroke-width:2px,color:#fff
    classDef output fill:#dc2626,stroke:#b91c1c,stroke-width:2px,color:#fff
    classDef support fill:#6b7280,stroke:#4b5563,stroke-width:1px,color:#fff
    
    class User,CLI primary
    class Agent,LLM,Generator secondary
    class Browser,Recorder tertiary
    class Scripts,Selenium,Playwright,Cypress output
    class Claude,Vision support
```

### Core Workflow

> Note: The diagrams are rendered using Mermaid. If they don't display correctly in your markdown viewer, you can copy the Mermaid code and paste it into the [Mermaid Live Editor](https://mermaid.live/) to view and export as images.

---

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
├── .env.example           # Example environment variables
└── README.md              # This file
```

---

## 🔍 Code Quality & Contributing

### Quality Checks Pipeline

This project maintains high code quality through automated checks that run on every pull request. All contributors should run these checks locally before submitting code.

#### Automated CI Pipeline

Our GitHub Actions workflow runs the following quality checks:

- **🧹 Code Linting** (flake8) - Style and syntax checking
- **🎨 Code Formatting** (black) - Consistent code formatting
- **🔍 Type Checking** (mypy) - Static type analysis
- **🧪 Unit Tests** (pytest) - Automated testing

### Running Quality Checks Locally

#### Prerequisites

Make sure you have the development dependencies installed:

```bash
# Install with development dependencies
pip install -e .[dev]

# Or install quality tools separately
pip install black flake8 mypy pytest
```

#### 1. Code Linting with flake8

**Check for style and syntax issues:**
```bash
flake8 src/ tests/
```

**Common flake8 errors and fixes:**

- **F401 - Unused import**: Remove the unused import
- **E302 - Missing blank lines**: Add 2 blank lines before top-level functions/classes
- **W291 - Trailing whitespace**: Remove spaces at end of lines
- **E304 - Blank line after decorator**: Remove blank line between decorator and function

#### 2. Code Formatting with black

**Check formatting:**
```bash
black --check src/ tests/
```

**Auto-fix formatting:**
```bash
black src/ tests/
```

#### 3. Type Checking with mypy

**Run type checking:**
```bash
mypy src/
```

**Common mypy errors and fixes:**

- **Argument type mismatch**: Use `# type: ignore[arg-type]` for known safe cases
- **Missing return type**: Add `-> ReturnType` to function signatures
- **Optional types**: Use `Optional[Type]` or `Type | None` for nullable values
- **Any return**: Cast with `str(result)` or use `# type: ignore[no-any-return]`

**Example mypy fixes:**
```python
# Before (mypy error)
def process_data(data):
    return data.upper()

# After (mypy clean)
def process_data(data: str) -> str:
    return data.upper()

# For complex cases, use type ignore
api_key = secret_key.get_secret_value()  # type: ignore[arg-type]
```

#### 4. Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=src/
```

### Quick Quality Check Script

Run all quality checks at once:

```bash
#!/bin/bash
echo "🧹 Running flake8..."
flake8 src/ tests/

echo "🎨 Checking black formatting..."
black --check src/ tests/

echo "🔍 Running mypy..."
mypy src/

echo "🧪 Running tests..."
pytest

echo "✅ All quality checks passed!"
```

Save this as `quality_check.sh` and run with `bash quality_check.sh`.

### Pre-commit Hooks (Recommended)

Install pre-commit hooks to automatically run quality checks:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks (if .pre-commit-config.yaml exists)
pre-commit install

# Run on all files
pre-commit run --all-files
```

### Fixing Quality Issues

#### Auto-fixable Issues

Some issues can be automatically fixed:

```bash
# Auto-format code
black src/ tests/

# Auto-fix some flake8 issues
autopep8 --in-place --recursive src/ tests/
```

#### Manual Fixes Required

- **Type annotations**: Add proper type hints
- **Unused imports**: Remove or use the imports
- **Complex logic**: Refactor for clarity
- **Missing docstrings**: Add documentation

### Quality Standards

- **Line length**: Maximum 88 characters (black default)
- **Type coverage**: All public functions should have type hints
- **Test coverage**: Aim for >80% code coverage
- **Documentation**: Public APIs should have docstrings

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Run quality checks locally** (see section above)
4. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
5. Push to the branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📧 Contact

Thusara Jayasinghe 

Project Link: [https://github.com/talk2silicon/talk2browser](https://github.com/talk2silicon/talk2browser)
