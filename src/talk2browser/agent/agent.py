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
from langgraph.graph import StateGraph, END, START
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
SYSTEM_PROMPT = """You are a helpful AI assistant that can control a web browser to complete multi-step tasks.

## Core Capabilities:
- Web navigation (URLs, links, buttons, forms)
- Form filling and submission
- Content extraction and summarization
- Multi-step task execution

## Guidelines:
1. When a full URL is provided, use page_goto to navigate directly to that URL
2. For search queries, prefer using DuckDuckGo (https://duckduckgo.com)
3. Always check the current page state before taking actions
4. Be specific in your searches to get the most relevant results
5. If a task fails, try to understand why and take appropriate action
6. When typing text, ensure the target element is visible and interactable
7. For multi-step tasks, complete one step at a time and verify success before proceeding
8. When asked to find and interact with elements, first analyze the page structure
9. If an action doesn't work as expected, try alternative approaches
10. Always verify the result of each action before proceeding to the next step

## Multi-step Navigation:
- Clearly identify each step before executing it
- Verify the success of each step before proceeding
- If a step fails, analyze why and try an alternative approach
- Maintain context between steps to ensure continuity

## Error Handling:
- If an element is not found, check for iframes, modals, or dynamic content
- If a page doesn't load, try refreshing or going back and retrying
- If stuck, analyze the page structure and try a different approach
"""

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
        workflow.add_node("chatbot", self._chatbot)  # For context and element scanning
        workflow.add_node("tools", tool_node)      # For tool execution
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "chatbot",
            self._route_tools,
            {"tools": "tools", END: END}
        )
        
        # Any time a tool is called, we return to the chatbot
        workflow.add_edge("tools", "chatbot")
        workflow.add_edge(START, "chatbot")
        
        # Set entry point to chatbot for initial context gathering
        workflow.set_entry_point("chatbot")
        
        logger.debug("Created agent graph with ToolNode and conditional routing")
        return workflow.compile()
    
    def _route_tools(self, state: AgentState):
        """Route to tools node if tool calls are present, otherwise end."""
        if not (messages := state.get("messages", [])):
            raise ValueError("No messages found in state")
            
        ai_message = messages[-1]
        
        # Count tool calls to prevent infinite loops
        tool_call_count = sum(
            1 for msg in messages 
            if hasattr(msg, "tool_calls") and msg.tool_calls
        )
        
        # Limit maximum tool calls
        MAX_TOOL_CALLS = 10
        if tool_call_count >= MAX_TOOL_CALLS:
            logger.warning(f"Reached maximum tool calls ({MAX_TOOL_CALLS}), ending conversation")
            return END
        
        # Check if the last message has tool calls
        if hasattr(ai_message, "tool_calls") and ai_message.tool_calls:
            return "tools"
        
        # No tool calls
        return END

    
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
            
            # Create system message content
            system_content = "\n\n".join([
                SYSTEM_PROMPT,
                "Current page state:",
                "\n".join(context)
            ])
            
            # Find and update existing system message or insert at start
            system_found = False
            for i, msg in enumerate(messages):
                if isinstance(msg, SystemMessage):
                    messages[i] = SystemMessage(content=system_content)
                    system_found = True
                    break
            
            if not system_found:
                messages.insert(0, SystemMessage(content=system_content))
            
            logger.debug(f"Updated message history with {len(messages)} messages")
            
            # Bind static tools to the LLM and get response
            llm_with_tools = self.llm.bind_tools(TOOLS)
            response = await llm_with_tools.ainvoke(messages)
            
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
