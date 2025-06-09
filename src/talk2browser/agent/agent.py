"""
Browser Agent implementation using LangGraph for browser automation.

This module provides a stateful agent that can process natural language instructions
and execute browser automation tasks using Playwright.
"""
import logging
import os
from typing import Any, Dict, List, Optional, TypedDict, Annotated, Sequence

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ..browser import PlaywrightClient
from ..tools.registry import ToolRegistry

# Configure logging
logger = logging.getLogger(__name__)

# System prompt template
SYSTEM_PROMPT = """You are a browser automation assistant that executes web tasks using Playwright.

Guidelines:
1. Navigate directly to URLs with page.goto
2. Use page.locator() for element selection
3. Verify element existence before interactions
4. Handle dynamic content and loading states
5. Add appropriate waits between actions
6. Report errors clearly and suggest fixes

Focus on completing tasks efficiently and reliably."""


class AgentState(TypedDict):
    """State for the browser agent.
    
    Note: Only contains serializable data. Page and browser access is managed
    through the BrowserAgent instance.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    current_url: Optional[str]
    next: str  # Next node to execute

class BrowserAgent:
    """Agent for browser automation using LangGraph and Playwright."""
    
    def __init__(self, llm: Optional[BaseChatModel] = None, headless: bool = False):
        """Initialize the browser agent.
        
        Args:
            llm: The language model to use (default: ChatAnthropic with claude-3-opus-20240229)
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.llm = llm or ChatAnthropic(
            model="claude-3-opus-20240229",
            temperature=0.1,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.client = None
        self.tool_registry = ToolRegistry(llm=self.llm)
        self.graph = self._create_agent_graph()
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.client is None:
            self.client = PlaywrightClient(headless=self.headless)
            await self.client.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client is not None:
            await self.client.close()
            self.client = None
    
    def _create_agent_graph(self):
        """Create and compile the LangGraph state graph."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("chatbot", self._chatbot)
        workflow.add_node("tools", self._execute_tools)
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "chatbot",
            self._route_tools,
            {"tools": "tools", END: END}
        )
        
        # Any time a tool is called, we return to the chatbot to decide the next step
        workflow.add_edge("tools", "chatbot")
        workflow.add_edge(START, "chatbot")
        
        # Set entry point and compile
        workflow.set_entry_point("chatbot")
        return workflow.compile()
    
    async def _chatbot(self, state: AgentState):
        """Process messages with LLM and determine next step."""
        messages = state["messages"]
        
        try:
            # Get current page state
            page_state = await self.client.get_page_state()
            state["current_url"] = page_state.get("url")
            
            # Add system prompt if not present
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                system_msg = SystemMessage(
                    content=f"""{SYSTEM_PROMPT}
                    
                    Current page: {page_state.get('url', 'No page loaded')}
                    Title: {page_state.get('title', '')}
                    """.strip()
                )
                messages = [system_msg] + list(messages)
            
            # Get available tools
            tools = self.tool_registry.list_tools()
            
            # Prepare tools in Anthropic format
            anthropic_tools = [{
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}})
                }
            } for tool in tools]
            
            # Bind tools to the model
            model_with_tools = self.llm.bind_tools(anthropic_tools)
            
            # Invoke the model and get response
            response = await model_with_tools.ainvoke(messages)
            
            # Check for tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"Found {len(response.tool_calls)} tool calls")
                state["next"] = "tools"
            else:
                state["next"] = END
                
            return {"messages": messages + [response]}
            
        except Exception as e:
            logger.error(f"Error in chatbot: {e}")
            state["next"] = END
            return {"messages": messages + [HumanMessage(content=f"Error: {str(e)}")]}
    
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
        
    async def _execute_tools(self, state: AgentState):
        """Execute tools and return updated state."""
        messages = state["messages"]
        last_msg = messages[-1]
        
        # Execute each tool call
        for tool_call in last_msg.tool_calls:
            try:
                # Get tool info
                name = tool_call["name"]
                args = tool_call["args"]
                tool_id = tool_call["id"]
                
                # Execute tool with page from client
                result = await self.tool_registry.execute_tool(
                    name,
                    **args,
                    _page=self.client.page
                )
                
                # Add tool result to messages
                messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                    tool_name=name
                ))
                
            except Exception as e:
                # Log error and continue
                logger.error(f"Error executing tool {name}: {e}")
                messages.append(ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_id,
                    tool_name=name
                ))
        
        # Return updated state
        return {"messages": messages}

    async def run(
        self, 
        task: str, 
        output_script: Optional[str] = None,
        **kwargs
    ) -> str:
        """Run the agent with the given task.
        
        Args:
            task: The task to perform
            output_script: Optional path to save the generated Playwright script
            **kwargs: Additional arguments to pass to the agent
            
        Returns:
            The agent's response
        """
        if not self.client or not self.client.page:
            raise RuntimeError("Agent is not initialized. Use 'async with' context manager.")
            
        try:
            # Run the agent
            result = await self.graph.ainvoke({
                "messages": [("user", task)],
                "page": self.client.page,
                "tool_registry": self.tool_registry,
                **kwargs
            })
            
            # Generate Playwright script if requested
            if output_script and hasattr(self.tool_registry, 'generate_playwright_script'):
                try:
                    script_path = await self.tool_registry.generate_playwright_script(
                        output_path=output_script,
                        llm=self.llm
                    )
                    print(f"\nGenerated Playwright script: {script_path}")
                except Exception as e:
                    logger.error(f"Failed to generate Playwright script: {e}")
            
            logger.info("Agent graph execution completed")
            
            # Get the final response
            last_message = result["messages"][-1]
            if hasattr(last_message, 'content'):
                response = last_message.content
            else:
                response = "I've completed the task."
                
            logger.info(f"Agent response: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Error in agent execution: {e}", exc_info=True)
            return f"An error occurred: {str(e)}"
