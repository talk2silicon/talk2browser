"""
Browser Agent implementation using LangGraph for browser automation.

This module provides a stateful agent that can process natural language instructions
and execute browser automation tasks using Playwright.
"""
import os
import logging
from typing import Annotated, Sequence, TypedDict, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..browser import PlaywrightClient
from ..browser.dom.service import DOMService
from ..tools.browser_tools import (
    navigate, click, fill, press, select_option, hover, 
    screenshot, wait_for_selector, get_text, 
    get_attribute, is_visible, set_page
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define available tools for the agent
TOOLS = [
    navigate, 
    click, 
    fill, 
    press, 
    select_option, 
    hover, 
    screenshot, 
    wait_for_selector, 
    get_text, 
    get_attribute, 
    is_visible
    # Do NOT expose evaluate or list_interactive_elements to the LLM
]

# System prompt template
SYSTEM_PROMPT = """You are BrowserAgent, a browser automation AI. Use the provided tools to interact with the web page. Always use the provided interactive element context to reference elements by their #hash. Never call a tool to list elements; this information is always included for you in your context after every action.

You must never ask for CSS selectors or XPaths. You must always use the provided #hash for any element interaction. If you do not see a #hash for an element, ask the user to reload the interactive element list.

Guidelines:
1. Interact with elements using their hashes (e.g., #abc123)
2. Always verify element visibility and interactivity
3. Handle dynamic content and loading states
4. Add appropriate waits between actions
5. Report errors clearly and suggest fixes

Available element attributes in the format:
#hash - tag_name [id=id_value] [name=name_value] [text=preview...] [hidden] [non-interactive]

Example usage:
- To click an element: click("#abc123")
- To fill a field: fill("#def456", "some text")
- To get text: get_text("#abc123")



Focus on completing tasks efficiently and reliably."""

class AgentState(TypedDict):
    """State for the browser agent following LangGraph pattern."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str  # For LangGraph routing

class BrowserAgent:
    """Agent for browser automation using LangGraph and Playwright."""
    
    def __init__(self, llm: Optional[ChatAnthropic] = None, headless: bool = False):
        """Initialize the browser agent.
        
        Args:
            llm: Optional ChatAnthropic instance. If not provided, a default one will be created.
            headless: Whether to run the browser in headless mode.
        """
        self.headless = headless
        
        # Initialize LLM
        self.llm = llm or ChatAnthropic(
            model=os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"),
            temperature=0.0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        # Initialize browser client and DOM service (will be started in __aenter__)
        self.client = PlaywrightClient(headless=headless)
        self.dom_service = None
        
        # Initialize graph
        self.graph = self._create_agent_graph()
        
        logger.info("BrowserAgent initialized with %s", self.llm.__class__.__name__)
    
    async def __aenter__(self):
        """Async context manager entry."""
        try:
            # Start the browser
            logger.debug("Starting browser...")
            await self.client.start()
            
            if not self.client.page:
                raise RuntimeError("Failed to create browser page")
            
            # Wait for page to be fully loaded
            await self.client.page.wait_for_load_state("domcontentloaded")
            await self.client.page.wait_for_load_state("networkidle")
            
            # Set up the page for browser tools
            set_page(self.client.page)
            
            # Initialize DOM service
            logger.info("Initializing DOM service...")
            self.dom_service = DOMService(self.client.page)
            
            # Initial scan for interactive elements
            logger.info("Performing initial element scan...")
            elements = await self.dom_service.get_interactive_elements(highlight=True)
            
            # Get formatted elements and map
            elements_str, element_map = self.dom_service.format_elements()
            logger.info(f"Found {len(elements)} elements, map size: {len(element_map)}")
            
            logger.info("Browser and DOM service initialized successfully")
            return self
            
        except Exception as e:
            logger.error("Failed to initialize browser: %s", str(e), exc_info=True)
            await self.__aexit__(type(e), e, None)  # Clean up on error
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if hasattr(self, 'client') and self.client:
            try:
                await self.client.close()
                logger.info("Browser client closed successfully")
            except Exception as e:
                logger.warning("Error closing browser client: %s", str(e))
    
    def _create_agent_graph(self):
        """Create the two-node LangGraph for the agent.
        Uses ToolNode for browser automation tools and chatbot for context management.
        """
        logger.info("Creating agent graph with ToolNode")
        workflow = StateGraph(AgentState)
        
        # Create tool node with browser tools
        tool_node = ToolNode(tools=TOOLS)
        
        # Add nodes
        workflow.add_node("agent", self._chatbot)  # For context and element scanning
        workflow.add_node("tools", tool_node)      # For tool execution
        
        # Add edges for back-and-forth between nodes
        workflow.add_edge("agent", "tools")
        workflow.add_edge("tools", "agent")
        
        # Set entry point to agent for initial context gathering
        workflow.set_entry_point("agent")
        
        logger.debug("Created agent graph with ToolNode for browser automation")
        return workflow.compile()
    
    def _route_tools(self, state: AgentState) -> str:
        """Route to tools if needed, otherwise end."""
        if not state.get("messages"):
            logger.debug("No messages in state, ending workflow")
            return END
            
        last_message = state["messages"][-1]
        logger.debug(f"Routing decision for message type: {type(last_message).__name__}")
        
        # Extract text content from the message
    async def _chatbot(self, state: AgentState) -> AgentState:
        """Process messages with LLM and determine next step with full context.
        Handles page state, interactive elements, and LLM interaction.
        """
        messages = state["messages"]
        
        try:
            # Get page state
            logger.info("Getting current page state")
            page_state = await self.client.get_page_state()
            current_url = page_state.get('url', 'No page loaded')
            current_title = page_state.get('title', '')
            
            # Get interactive elements if DOM service is available
            elements_context = ""
            element_map = {}
            
            if self.dom_service:
                try:
                    # Refresh interactive elements
                    logger.info("Refreshing interactive elements...")
                    await self.dom_service.get_interactive_elements(highlight=True)
                    
                    # Get formatted elements and map
                    elements_context, element_map = self.dom_service.format_elements()
                    logger.info(f"Retrieved {len(element_map)} interactive elements")
                    
                    # Add element map to state for tools
                    state["element_map"] = element_map
                    logger.debug(f"Added element map to state")
                    
                except Exception as e:
                    logger.error(f"Error getting interactive elements: {e}", exc_info=True)
                    elements_context = f"Error scanning elements: {str(e)}"
            else:
                logger.warning("No DOM service available")
                elements_context = "DOM service not initialized"
            
            # Build context for LLM
            context = [
                f"Current URL: {current_url}",
                f"Page title: {current_title}",
                elements_context
            ]
            
            # Add context message
            messages.append(
                SystemMessage(
                    content="\n\n".join([
                        SYSTEM_PROMPT,
                        "Current page state:",
                        "\n".join(context)
                    ])
                )
            )
            
            # Get response from LLM
            response = await self.llm.ainvoke(messages)
            
            # Check if response has tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info("Tool calls detected in LLM response")
                return {
                    "messages": messages + [response],
                    "next": "tools"
                }
            
            # No tool calls, end the conversation
            logger.info("No tool calls in LLM response, ending conversation")
            return {
                "messages": messages + [response],
                "next": END
            }
            
        except Exception as e:
            error_msg = f"Error in chatbot: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "messages": messages + [SystemMessage(content=error_msg)],
                "next": END
            }
    
    async def run(self, task: str) -> str:
        """Run the agent with the given task.
        
        Args:
            task: The task or query for the agent.
            
        Returns:
            The agent's response as a string.
        """
        try:
            # Initialize state
            initial_state = AgentState(
                messages=[HumanMessage(content=task)],
                next="agent"
            )
            
            # Run the graph
            logger.info(f"Starting agent with task: {task}")
            result = await self.graph.ainvoke(initial_state)
            
            # Get final response
            messages = result["messages"]
            last_message = messages[-1]
            
            # Extract content from last message
            response = last_message.content if hasattr(last_message, 'content') else str(last_message)
            logger.info("Agent task completed")
            
            return response
            
        except Exception as e:
            error_msg = f"Error running agent: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
