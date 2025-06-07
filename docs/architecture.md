# talk2browser Architecture

## Overview

talk2browser is a self-improving browser automation tool built on Playwright and LangGraph. It uses LLMs to understand natural language instructions, select appropriate browser automation tools, and execute multi-step workflows.

## Core Components

### 1. Browser Module

The browser module provides a clean abstraction over Playwright for browser automation:

```
src/talk2browser/browser/
├── client.py         # PlaywrightClient for browser lifecycle management
└── element_utils.py  # Element discovery and interaction utilities
```

#### PlaywrightClient

The `PlaywrightClient` class manages the browser lifecycle and provides methods for:
- Browser initialization and cleanup
- Page navigation and state management
- Element interaction (click, type, etc.)
- Context extraction for LLM decision-making

It implements an async context manager pattern for clean resource management:

```python
async with PlaywrightClient(headless=False) as browser:
    await browser.page.goto("https://example.com")
    elements = await browser.discover_elements()
```

#### Element Utils

The `element_utils.py` module provides utilities for:
- Discovering interactive elements on a page
- Generating stable selectors for elements
- Extracting element properties for LLM context
- Optional visual highlighting for debugging

### 2. Tools Module

The tools module manages the available browser automation tools:

```
src/talk2browser/tools/
├── registry.py       # Dynamic tool discovery and registration
└── custom_tools.py   # Domain-specific custom tools
```

#### ToolRegistry

The `ToolRegistry` class is responsible for:
- Dynamically discovering and registering tools
- Providing tool metadata for LLM selection
- Tool execution and parameter validation
- Extensibility through custom tools

Tools are defined with:
- Name: Unique identifier
- Function: Callable implementation
- Description: Human-readable explanation
- Parameters: JSON schema for validation

### 3. Agent Module

The agent module integrates LangGraph for workflow orchestration:

```
src/talk2browser/agent/
└── agent.py          # BrowserAgent with LangGraph integration
```

#### BrowserAgent

The `BrowserAgent` class orchestrates the entire system:
- Creates and manages the LangGraph workflow
- Processes natural language instructions
- Selects appropriate tools based on context
- Executes tools and handles results
- Provides feedback to the user

### 4. Utils Module

The utils module provides shared utilities:

```
src/talk2browser/utils/
└── logging.py        # Logging configuration
```

## LangGraph Integration

talk2browser uses a two-node LangGraph architecture:

1. **Tool Selection Node**: Processes user instructions and selects the appropriate tool
2. **Tool Execution Node**: Executes the selected tool and handles the result

The graph is defined in `BrowserAgent._create_agent_graph()`:

```python
workflow = StateGraph(AgentState)
workflow.add_node("select_tool", self._select_tool)
workflow.add_node("execute_tool", self._execute_tool)
workflow.set_entry_point("select_tool")
workflow.add_edge("execute_tool", "select_tool")
workflow.add_conditional_edges(
    "select_tool",
    self._should_continue,
    {"continue": "execute_tool", "end": END}
)
```

## Data Flow

1. User provides a natural language instruction
2. BrowserAgent initializes the state with the instruction
3. Tool Selection Node selects the appropriate tool based on:
   - User instruction
   - Current page context
   - Available tools
4. Tool Execution Node executes the selected tool
5. Results are recorded and used to update the state
6. The process repeats until completion or error

## Self-Improvement Mechanism

In future iterations, talk2browser will implement a self-improvement mechanism:

1. **Pattern Detection**: Identify repeated sequences of actions
2. **Tool Generation**: Create new composite tools from patterns
3. **Tool Registry Update**: Register new tools for future use

## Error Handling

talk2browser implements robust error handling:
- Graceful recovery from browser errors
- Detailed error messages for debugging
- Automatic retry for transient failures
- Comprehensive logging for troubleshooting

## Configuration

Configuration is managed through environment variables and defaults:
- Browser settings (headless mode, browser type)
- LLM settings (model, API keys)
- Logging settings (level, output)
- Timeout settings

## Extension Points

talk2browser is designed for extensibility:
- Custom tools can be added to `custom_tools.py`
- Element discovery can be extended with new selectors
- LLM integration can be swapped with different providers
- Additional LangGraph nodes can be added for complex workflows
