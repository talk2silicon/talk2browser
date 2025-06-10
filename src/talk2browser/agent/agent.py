"""
Browser Agent implementation using LangGraph for browser automation.

This module provides a stateful agent that can process natural language instructions
and execute browser automation tasks using Playwright.
"""
import os
import logging
from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any, Tuple, cast
import logging
import asyncio
import traceback
from typing import Any, Dict, Tuple, List, Optional

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

Available Tools:
- navigate(url): Navigate to a URL
- click(selector): Click on an element (use hash like #abc123)
- fill(selector, text): Fill a form field (use hash like #abc123)
- press(selector, key): Press a key in an element
- select_option(selector, value): Select an option from a dropdown
- hover(selector): Hover over an element
- screenshot(full_page=False): Take a screenshot
- evaluate(script): Execute JavaScript
- wait_for_selector(selector, timeout=30000): Wait for an element
- get_text(selector): Get text content
- get_attribute(selector, attribute): Get an attribute value
- is_visible(selector): Check if element is visible

Focus on completing tasks efficiently and reliably."""

class AgentState(TypedDict):
    """State for the browser agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    interactive_elements: Dict[str, str]  # Maps element hashes to XPaths
    dom_service: Optional[Any] = None  # Will hold the DOMService instance
    tool_call_count: int = 0  # Track number of tool calls to prevent infinite loops

class BrowserAgent:
    """Agent for browser automation using LangGraph and Playwright."""
    
    def __init__(self, llm: Optional[ChatAnthropic] = None, headless: bool = False):
        """Initialize the browser agent.
        
        Args:
            llm: The language model to use
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        
        # Get API key from environment
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            
        # Initialize LLM
        self.llm = llm or ChatAnthropic(
            model="claude-3-opus-20240229",
            temperature=0.1,
            api_key=self.api_key
        )
        
        self.client = None
        
        # Create the agent graph
        self.graph = self._create_agent_graph()
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.client is None:
            self.client = PlaywrightClient(headless=self.headless)
            await self.client.start()
            
            # Set up the page for browser tools
            if self.client.page:
                set_page(self.client.page)
                
                # Initialize DOM service
                if hasattr(self.client, 'page') and self.client.page:
                    from ..browser.dom.service import DOMService
                    self.dom_service = DOMService(self.client.page)
                    logger.info("Initialized DOM service with page")
                else:
                    logger.warning("No page available for DOM service initialization")
                
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client is not None:
            try:
                await self.client.close()
            except Exception as e:
                logger.warning(f"Error closing browser client: {e}")
            finally:
                self.client = None
    
    def _create_agent_graph(self):
        """Create and configure the LangGraph for the agent."""
        graph_builder = StateGraph(AgentState)
        
        # Add nodes
        graph_builder.add_node("chatbot", self._chatbot)
        
        # Create the ToolNode with the tools list
        tool_node = ToolNode(TOOLS)
        graph_builder.add_node("tools", tool_node)
        
        # Set entry point
        graph_builder.set_entry_point("chatbot")
        
        # Add conditional edges
        graph_builder.add_conditional_edges(
            "chatbot",
            self._route_tools,
            {
                "tools": "tools",
                END: END
            }
        )
        
        # Add edge from tools back to chatbot
        graph_builder.add_edge("tools", "chatbot")
        
        # Compile the graph
        logger.info("Compiling browser agent graph")
        return graph_builder.compile()
    
    def _route_tools(self, state: AgentState):
        """Route to tools if needed, otherwise end."""
        if not state.get("messages"):
            logger.debug("No messages in state, ending workflow")
            return END
            
        last_message = state["messages"][-1]
        logger.debug(f"Last message type: {type(last_message).__name__}")
        
        # Prevent infinite recursion by limiting tool calls
        MAX_TOOL_CALLS = 25
        tool_call_count = state.get("tool_call_count", 0)
        
        if tool_call_count >= MAX_TOOL_CALLS:
            logger.warning(f"Reached maximum tool calls ({MAX_TOOL_CALLS}), ending conversation")
            return END
        
        # Check for tool calls in the message (OpenAI format)
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(f"Tool calls detected: {last_message.tool_calls}")
            return "tools"
            
        # Check for AIMessage with tool_calls attribute (LangChain format)
        if hasattr(last_message, 'additional_kwargs') and 'tool_calls' in last_message.additional_kwargs:
            tool_calls = last_message.additional_kwargs['tool_calls']
            if tool_calls:
                logger.info(f"Tool calls detected (LangChain format): {tool_calls}")
                return "tools"
        
        # If no tool calls, end the workflow
        logger.info("No tool calls detected, ending workflow")
        return END
    
    async def _get_page_and_elements(self) -> Tuple[str, str, str, Dict[str, str]]:
        """Get current page state and interactive elements."""
        page_state = await self.client.get_page_state()
        current_url = page_state.get('url', 'No page loaded')
        current_title = page_state.get('title', '')
        
        logger.info(f"Getting page state - URL: {current_url}, Title: {current_title}")
        
        # Get interactive elements if we have a DOM service
        elements_context = ""
        element_map = {}
        
        if hasattr(self, 'dom_service') and self.dom_service:
            try:
                logger.info("Scanning page for interactive elements...")
                elements = await self.dom_service.get_interactive_elements(highlight=True)
                logger.debug(f"[DOMSCAN] Raw elements found: {len(elements)}")
                for idx, el in enumerate(elements):
                    logger.debug(f"[DOMSCAN] Raw Element {idx+1}: tag={el.tag_name}, type={el.attributes.get('type')}, id={el.attributes.get('id')}, name={el.attributes.get('name')}, text='{el.text[:50] if el.text else ''}', is_visible={el.is_visible}, is_interactive={el.is_interactive}")
                filtered_elements = [el for el in elements if el.is_interactive and el.is_visible]
                logger.debug(f"[DOMSCAN] Filtered interactive+visible elements: {len(filtered_elements)}")
                for idx, el in enumerate(filtered_elements):
                    logger.debug(f"[DOMSCAN] Kept Element {idx+1}: tag={el.tag_name}, type={el.attributes.get('type')}, id={el.attributes.get('id')}, name={el.attributes.get('name')}, text='{el.text[:50] if el.text else ''}'")
                element_descriptions = []
                for idx, element in enumerate(filtered_elements):
                    element_hash = f"#{element.element_hash[:6]}"
                    element_map[element_hash] = element.xpath
                    desc = f"{idx + 1}. {element_hash} - {element.tag_name}"
                    if element.attributes.get('id'):
                        desc += f" id={element.attributes['id']}"
                    if element.attributes.get('name'):
                        desc += f" name={element.attributes['name']}"
                    if element.attributes.get('type'):
                        desc += f" type={element.attributes['type']}"
                    if element.text:
                        text_preview = element.text[:30] + ('...' if len(element.text) > 30 else '')
                        desc += f" text='{text_preview}'"
                    if not element.is_visible:
                        desc += " (hidden)"
                    if not element.is_interactive:
                        desc += " (non-interactive)"
                    element_descriptions.append(desc)
                logger.info(f"Mapped {len(element_map)} elements with hashes")
                elements_context = "\n".join([
                    "Interactive elements on the page (use #hash to reference):",
                    *element_descriptions,
                    f"\nTotal interactive elements: {len(filtered_elements)}"
                ])
                return current_url, current_title, elements_context, element_map
            except Exception as e:
                logger.error(f"Error getting interactive elements: {e}", exc_info=True)
                return current_url, current_title, f"Error getting interactive elements: {str(e)}", element_map  # Return existing element_map
        else:
            return current_url, current_title, "", element_map  # Return the element_map instead of empty dict
    
    async def _chatbot(self, state: AgentState):
        """Process messages with LLM and determine next step with full context."""
        messages = state["messages"]
        
        try:
            # Get current page state
            page_state = await self.client.get_page_state()
            state["current_url"] = page_state.get("url")
            
            # Get user input from messages
            user_input = next((msg.content for msg in messages[::-1] 
                             if isinstance(msg, HumanMessage)), "")
            
            # Get interactive elements and create element map
            current_url, current_title, elements_context, element_map = await self._get_page_and_elements()
            
            # Update page state with interactive elements
            page_state['interactive_elements'] = [
                el for el in element_map.values()
                if isinstance(el, dict) and 'xpath' in el
            ]
            
            # Format interactive elements for context
            elements_context = self._format_elements(page_state.get('interactive_elements', []))
            
            # Format conversation history
            conversation_history = self._format_history(messages)
            
            # Build enhanced system message with full context
            system_msg = SystemMessage(
                content=f"""{SYSTEM_PROMPT}
                
                ## Current Page Context
                URL: {page_state.get('url', 'No page loaded')}
                Title: {page_state.get('title', '')}
                
                ## Interactive Elements
                {elements_context}
                
                ## Conversation History
                {conversation_history}
                
                ## Available Tools
                {self._format_tools(TOOLS)}
                """.strip()
            )
            
            # Prepare conversation with updated context
            conversation = [system_msg] + [
                msg for msg in messages 
                if not isinstance(msg, SystemMessage)
            ]
            
            # Prepare model with tools
            model_with_tools = self.llm.bind_tools(TOOLS)
            
            # Call LLM
            logger.info("Sending message to LLM with updated context...")
            response = await model_with_tools.ainvoke(conversation)
            logger.debug(f"Received response from LLM: {response}")
            
            # Process tool calls if any
            tool_calls = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_calls = response.tool_calls
            elif hasattr(response, "additional_kwargs") and "tool_calls" in response.additional_kwargs:
                tool_calls = response.additional_kwargs["tool_calls"]
            
            if tool_calls:
                # Inject element map into tool calls
                self._inject_element_map_into_tool_calls(tool_calls, element_map)
                tool_call_count = state.get("tool_call_count", 0) + 1
                logger.info(f"Tool call detected, count: {tool_call_count}")
                logger.debug(f"Tool calls: {tool_calls}")
                state["tool_call_count"] = tool_call_count
            
            # Add AI response to messages
            messages.append(response)
            
            return {
                "messages": messages,
                "interactive_elements": element_map,
                "tool_call_count": state.get("tool_call_count", 0),
                "dom_service": getattr(self, "dom_service", None)
            }
            
            except Exception as llm_error:
                error_msg = f"Error calling LLM: {str(llm_error)}"
                logger.error(error_msg, exc_info=True)
                return {
                    "messages": messages + [ToolMessage(content=error_msg, name="error")],
                    "interactive_elements": element_map,
                    "tool_call_count": tool_call_count,
                    "dom_service": getattr(self, "dom_service", None)
                }
        
        except Exception as e:
            error_msg = f"Error in chatbot: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "messages": messages + [ToolMessage(content=error_msg, name="error", tool_call_id="error_0")],
                "interactive_elements": state.get("interactive_elements", {}),
                "tool_call_count": tool_call_count
            }
    
    def _ensure_system_prompt(self, messages: List[BaseMessage], current_url: str, current_title: str, elements_context: str = "") -> List[BaseMessage]:
        """Ensure system prompt is present in messages and contains current context."""
        # Remove any existing system messages
        messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        # Create new system message with current context
        system_msg = SystemMessage(
            content=f"""{SYSTEM_PROMPT}
            
            Current page: {current_url}
            Title: {current_title}
            
            {elements_context}
            """
        )
        
        # Add the new system message at the beginning
        return [system_msg] + messages
    
    def _inject_element_map_into_tool_calls(self, tool_calls: List[Dict[str, Any]], element_map: Dict[str, str]) -> None:
        """Inject element_map into browser tool calls."""
        for tool_call in tool_calls:
            tool_func = next((t for t in TOOLS if getattr(t, "name", None) == tool_call.get("name")), None)
            if tool_func and getattr(tool_func, "_is_browser_tool", False):
                tool_call["args"]["element_map"] = element_map
    
    async def run(self, task: str, **kwargs) -> str:
        """Run the agent with the given task.
        
        Args:
            task: The task or query for the agent.
            **kwargs: Additional arguments to pass to the agent.
            
        Returns:
            The agent's response as a string.
        """
        try:
            # Initialize state with the user's task
            initial_state = {
                "messages": [HumanMessage(content=task)]
            }
            
            # Run the graph
            result = await self.graph.ainvoke(initial_state)
            
            # Extract the final response
            last_message = result["messages"][-1]
            if hasattr(last_message, 'content'):
                return last_message.content
            return str(last_message)
            
        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return f"Error: {str(e)}"
