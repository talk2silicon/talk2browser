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
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ..browser import PlaywrightClient
from ..browser.dom.service import DOMService
from ..tools.registry import ToolRegistry

# Configure logging
logger = logging.getLogger(__name__)

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
    """State for the browser agent.
    
    Note: Only contains serializable data. Page and browser access is managed
    through the BrowserAgent instance.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    current_url: Optional[str]
    next: str  # Next node to execute

class BrowserAgent:
    """Agent for browser automation using LangGraph and Playwright."""
    
    def __init__(self, headless: bool = False, llm: Optional[BaseChatModel] = None):
        """Initialize the browser agent.
        
        Args:
            headless: Whether to run browser in headless mode
            llm: The language model to use (default: ChatAnthropic with claude-3-opus-20240229)
        """
        self.headless = headless
        self.llm = llm or ChatAnthropic(
            model=os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"),
            temperature=0.0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.client = None
        self.dom_service = None
        self.tool_registry = ToolRegistry()
        self.graph = self._create_agent_graph()
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.client is None:
            self.client = PlaywrightClient(headless=self.headless)
            await self.client.start()
            self.dom_service = DOMService(self.client.page)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client is not None:
            if self.dom_service:
                await self.dom_service.clear_highlights()
                self.dom_service = None
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
        """Process messages with LLM and determine next step with full context."""
        messages = state["messages"]
        
        try:
            # Get current page state
            page_state = await self.client.get_page_state()
            state["current_url"] = page_state.get("url")
            
            # Get user input from messages
            user_input = next((msg.content for msg in messages[::-1] 
                             if isinstance(msg, HumanMessage)), "")
            
            # Get available tools filtered by both user input and page state
            tools = self.tool_registry.list_tools(
                user_input=user_input,
                page_state=page_state,
                top_k=5
            )
            
            # Format interactive elements for context
            elements_context = self._format_elements(
                page_state.get('interactive_elements', [])
            )
            
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
                
                ## Available Tools (most relevant first)
                {self._format_tools(tools)}
                """.strip()
            )
            
            # Prepare conversation with updated context
            conversation = [system_msg] + [
                msg for msg in messages 
                if not isinstance(msg, SystemMessage)
            ]
            
            # Add tool results if any
            if len(messages) > 1 and any(isinstance(msg, ToolMessage) for msg in messages):
                # Get the most recent tool result
                tool_msg = next((msg for msg in messages[::-1] 
                                if isinstance(msg, ToolMessage)), None)
                if tool_msg:
                    conversation.append(HumanMessage(
                        content=f"Tool execution result: {tool_msg.content}\n\n"
                                "What should we do next?"
                    ))
            
            # Prepare tools in Anthropic format
            anthropic_tools = [{
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {
                        "type": "object", 
                        "properties": {}
                    })
                }
            } for tool in tools]
            
            # Bind tools and invoke model with full context
            model_with_tools = self.llm.bind_tools(anthropic_tools)
            response = await model_with_tools.ainvoke(conversation)
            
            return {"messages": conversation + [response]}
            
        except Exception as e:
            logger.error(f"Error in chatbot: {e}", exc_info=True)
            return {"messages": messages + [
                HumanMessage(content=f"Error: {str(e)}")
            ]}
            
    def _format_elements(self, elements: List[Dict]) -> str:
        """Format interactive elements for context."""
        if not elements:
            return "No interactive elements found"
        
        formatted = []
        for i, elem in enumerate(elements[:5], 1):
            desc = elem.get('description', 'No description')
            elem_type = elem.get('type', 'element')
            formatted.append(f"{i}. [{elem_type}] {desc}")
        
        if len(elements) > 5:
            formatted.append(f"... and {len(elements) - 5} more")
        
        return "\n".join(formatted)
    
    def _format_history(self, messages: List[BaseMessage]) -> str:
        """Format conversation history."""
        history = []
        for msg in messages[-3:]:  # Last 3 messages
            if isinstance(msg, HumanMessage):
                history.append(f"User: {msg.content}")
            elif isinstance(msg, ToolMessage):
                history.append(f"Tool: {msg.tool_name} -> {msg.content}")
            elif isinstance(msg, AIMessage):
                history.append(f"Assistant: {msg.content}")
        return "\n".join(history) if history else "No previous actions"
    
    def _format_tools(self, tools: List[Dict]) -> str:
        """Format tools list for context."""
        return "\n".join([
            f"- {tool['name']}: {tool['description']}" 
            for tool in tools
        ])
    
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

    async def run(self, prompt: str) -> str:
        """Run the agent with the given prompt.
        
        Args:
            prompt: User's natural language prompt
            
        Returns:
            Response from the agent
        """
        logger.info(f"Starting agent with prompt: {prompt}")
        
        # Initialize the browser if not already done
        if not self.client:
            self.client = PlaywrightClient(headless=self.headless)
            await self.client.start()
        
        try:
            # Create initial state with the user's prompt
            state = {
                "messages": [HumanMessage(content=prompt)],
                "current_url": None,
                "next": "chatbot"
            }
            
            logger.info(f"Starting agent with URL: {state['current_url'] or 'about:blank'}")
            
            # Run the graph
            logger.info("Executing agent graph...")
            result = await self.graph.ainvoke(state)
            
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
