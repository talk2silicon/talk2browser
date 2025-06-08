# src/talk2browser/agent/agent.py

# Standard library imports
import logging
import os
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict, Union

# Third-party imports
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import Tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Local application imports
from src.talk2browser.browser.client import PlaywrightClient
from src.talk2browser.tools.registry import ToolRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Define the system prompt
SYSTEM_PROMPT = """
You are an AI assistant that helps users automate browser interactions.
You have access to tools that can control a browser using Playwright.

When a user asks you to perform a task:
1. Select the most appropriate tool based on the user's request
2. Only ask for parameters that are explicitly marked as required in the tool description
3. The browser automation will handle all additional processing once triggered

If no tool matches the user's request, respond conversationally and explain what you can help with.
"""

# Define the state schema using the standard LangChain pattern
class AgentState(TypedDict):
    """State for the Browser AI Agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]

class BrowserAgent:
    """Agent for processing messages and executing browser automation tools using LangGraph."""

    def __init__(self, 
                 llm: Optional[BaseChatModel] = None,
                 headless: bool = False):
        """
        Initialize the agent with an optional LLM and browser configuration.

        Args:
            llm: The language model to use (default: ChatAnthropic with claude-3-opus-20240229)
            headless: Whether to run the browser in headless mode
        """
        # Set up the LLM
        self.llm = llm or ChatAnthropic(
            model=os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"),
            temperature=0.0,
            api_key=os.getenv("CLAUDE_API_KEY")
        )

        # Initialize Playwright client
        self.browser_client = PlaywrightClient(headless=headless)
        
        # Initialize tool registry
        self.tool_registry = ToolRegistry(browser_client=self.browser_client)

        # Initialize the graph
        self._initialize_graph()

        logger.info("Agent initialized with LLM: %s", self.llm.__class__.__name__)

    def _initialize_graph(self):
        logger.info("Initializing Browser Agent")

        # Discover browser tools
        self.tool_registry.discover_tools()
        logger.info("Creating LangGraph with the tools from the tool registry")
        self.graph = self._create_agent_graph()

    def _create_agent_graph(self) -> StateGraph:
        """Create the Browser AI Agent graph using the standard LangGraph pattern."""
        # Create the graph
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("chatbot", self._chatbot)

        # Get tools from the registry
        browser_tools = self.tool_registry.list_tools()
        
        # Create LangChain tools from the registry tools
        langchain_tools = []

        for tool_def in browser_tools:
            tool_name = tool_def.get('name')
            tool_description = tool_def.get('description', '')

            # Create a function to execute the tool
            def make_tool_executor(tool_name):
                def execute_tool(*args, **kwargs):
                    # Before executing, get page state for context
                    page_state = self.browser_client.get_page_state_sync()
                    
                    # Add page state to kwargs for context
                    kwargs['page_state'] = page_state
                    
                    # Execute the tool
                    result = self.tool_registry.execute_tool(tool_name, kwargs)
                    return result
                return execute_tool

            # Create the tool
            langchain_tool = Tool(
                name=tool_name,
                description=tool_description,
                func=make_tool_executor(tool_name)
            )

            langchain_tools.append(langchain_tool)

        # Create the ToolNode with the tools
        tool_node = ToolNode(langchain_tools)
        graph.add_node("tools", tool_node)

        # Set entry point
        graph.set_entry_point("chatbot")

        # Add conditional edge from chatbot to either tools or END
        graph.add_conditional_edges(
            "chatbot",
            self._route_tools,
            {"tools": "tools", END: END},
        )

        # Any time a tool is called, we return to the chatbot to decide the next step
        graph.add_edge("tools", "chatbot")
        graph.add_edge(START, "chatbot")

        # Compile the graph
        return graph.compile()

    def _chatbot(self, state: AgentState):
        """Process the user message and generate a response."""
        messages = state["messages"]

        # Get the tools from the registry
        tools = self.tool_registry.list_tools()

        # Get current page state for context
        page_state = self.browser_client.get_page_state_sync()
        
        # Format page state for the LLM
        page_state_text = self._format_page_state(page_state)
        
        # Add page state to the user's message
        enhanced_messages = list(messages)
        