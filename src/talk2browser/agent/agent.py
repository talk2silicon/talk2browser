"""
Browser Agent implementation using LangGraph for browser automation.

This module provides a stateful agent that can process natural language instructions
and execute browser automation tasks using Playwright.
"""
import os
import logging
from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from dotenv import load_dotenv, find_dotenv

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..browser import PlaywrightClient
from ..tools.browser_tools import navigate, click, set_page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define available tools for the agent
TOOLS = [navigate, click]

# System prompt template
SYSTEM_PROMPT = """You are a browser automation assistant that executes web tasks using Playwright.

Guidelines:
1. Navigate directly to URLs with page.goto
2. Use page.locator() for element selection
3. Verify element existence before interactions
4. Handle dynamic content and loading states
5. Add appropriate waits between actions
6. Report errors clearly and suggest fixes

Available Tools:
- navigate: Navigate to a URL
- click: Click on an element on the page

Focus on completing tasks efficiently and reliably."""

class AgentState(TypedDict):
    """State for the browser agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]

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
                
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client is not None:
            await self.client.close()
            self.client = None
    
    def _create_agent_graph(self):
        """Create and configure the LangGraph for the agent."""
        # Create the graph
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
            {"tools": "tools", END: END}
        )
        
        # Add edge from tools back to chatbot
        graph_builder.add_edge("tools", "chatbot")
        
        # Add edge from start to chatbot
        graph_builder.add_edge(START, "chatbot")
        
        # Compile the graph
        logger.info("Compiling browser agent graph")
        return graph_builder.compile()
    
    def _route_tools(self, state: AgentState):
        """Route to tools if needed, otherwise end."""
        if not state.get("messages"):
            return END
            
        last_message = state["messages"][-1]
        
        # Debug log the last message
        logger.debug(f"Last message: {last_message}")
        
        # Check for tool calls in the message
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(f"Routing to tools: {last_message.tool_calls}")
            return "tools"
            
        # Check for AIMessage with tool_calls attribute (LangChain format)
        if hasattr(last_message, 'additional_kwargs') and 'tool_calls' in last_message.additional_kwargs:
            logger.info(f"Routing to tools (LangChain format): {last_message.additional_kwargs['tool_calls']}")
            return "tools"
            
        logger.debug("No tool calls found, ending workflow")
        return END
    
    async def _chatbot(self, state: AgentState):
        """Process messages with LLM and determine next step."""
        messages = state["messages"]
        
        try:
            # Get current page state
            page_state = await self.client.get_page_state()
            
            # Add system prompt if not present
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                system_msg = SystemMessage(
                    content=f"""{SYSTEM_PROMPT}
                    
                    Current page: {page_state.get('url', 'No page loaded')}
                    Title: {page_state.get('title', '')}
                    """.strip()
                )
                messages = [system_msg] + list(messages)
            
            # Bind tools to the model for this invocation
            model_with_tools = self.llm.bind_tools(TOOLS)
            
            # Invoke the model with the full message history
            response = await model_with_tools.ainvoke(messages)
            
            # Log the response for debugging
            logger.debug(f"LLM response: {response}")
            
            # Return updated state with the response
            return {"messages": messages + [response]}
            
        except Exception as e:
            logger.error(f"Error in chatbot: {e}", exc_info=True)
            return {"messages": messages + [HumanMessage(content=f"Error: {str(e)}")]}
    
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
