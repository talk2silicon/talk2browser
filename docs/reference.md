"""Graph structure for the DevOps Copilot."""

import os
import logging
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Import course_tool functions
from src.course_tools.course_tool import get_courses, get_course_details, create_application, get_course_offerings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define available tools for the agent (keep only course-related tools)
TOOLS = [
    get_courses,
    get_course_details,
    create_application,
    get_course_offerings
]

# Define the system prompt
SYSTEM_PROMPT = """
You are Gradella Copilot, a helpful assistant guiding students step by step through the university course admission process. Your job is to:

- Greet the student and clearly explain the application steps.
- Show available university courses (fetched from Supabase, originally sourced from training.gov.au) using the get_courses tool.
- When responding with a list of courses, always enumerate and display each course, showing the qualification code, title, and description for each one. Do not summarize or skip the actual data. Use bullet points or a table if helpful for clarity.
- Example output:
  - CUA50920: Diploma of Photography and Digital Imaging — A qualification for aspiring professional photographers.
  - BSB50120: Diploma of Business — Prepares students for business management roles.
- When the student asks about providers, fees, locations, or wants to compare offerings for a course, use the get_course_offerings tool. Present the results as a readable comparison, showing provider names, campuses, delivery modes, fees, and start dates for each offering.
- Collect the student's personal information (name, email, phone, etc.) and validate it.
- Send a verification code to the student's email (and optionally via SMS).
- Prompt the student to enter the verification code and verify it.
- Guide the student to upload all required documents for their application.
- Save all application details, including documents and selected course, securely in Supabase.
- Answer any questions about courses, the process, or requirements in a friendly, supportive manner.
- Ensure privacy, security, and data accuracy at all times.

TOOLS AVAILABLE:
- get_courses: Fetch a list of available university courses. Use when the student asks about available courses, wants to search for courses, or requests course options.
- get_course_details: Fetch details for a specific course by its code. Use when the student asks for detailed course information, entry requirements, or course structure.
- create_application: Create a new student application. Use when the student wants to apply for a course or submit their application information.
- get_course_offerings: Fetch the course details and all provider offerings for a course (including provider info, fees, campuses, delivery modes, and start dates). Use when the student asks about providers, fees, locations, or wants to compare offerings for a course.

**Your goal is to make the process easy, clear, and reassuring for the student.**
"""

# Define the state schema using the standard LangChain pattern
class AgentState(TypedDict):
    """State for the DevOps Copilot."""
    messages: Annotated[Sequence[BaseMessage], add_messages]

def chatbot(state: AgentState):
    """Process the user message and generate a response."""
    logger.info("Chatbot processing message")
    
    messages = state["messages"]
    
    # Get the model
    api_key = os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("Claude API key not provided and CLAUDE_API_KEY environment variable not set")
    
    model_name = os.environ.get("CLAUDE_MODEL", "claude-3-opus-20240229")
    
    # Initialize the model
    model = ChatAnthropic(
        anthropic_api_key=api_key,
        model=model_name,
        temperature=0
    )
    
    # Bind tools to the model
    model_with_tools = model.bind_tools(TOOLS)
    
    # Check if the first message is a system message, if not, add it
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
    
    # Invoke the model with the full message history
    response = model_with_tools.invoke(messages)
    
    # Return the updated state with the full message history plus the response
    return {"messages": messages + [response]}

def route_tools(state: AgentState):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    
    Also prevents infinite recursion by counting tool calls in the message history.
    """
    if messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    
    # Count how many tool calls have been made in this conversation
    tool_call_count = sum(
        1 for msg in messages 
        if hasattr(msg, "tool_calls") and msg.tool_calls
    )
    
    # Prevent infinite recursion by limiting tool calls
    MAX_TOOL_CALLS = 25
    if tool_call_count >= MAX_TOOL_CALLS:
        logger.warning(f"Reached maximum tool calls ({MAX_TOOL_CALLS}), ending conversation")
        return END
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return END


def create_copilot_graph() -> StateGraph:
    """Create the DevOps Copilot graph using the standard LangGraph pattern."""
    logger.info("Creating DevOps Copilot graph")
    
    # Create the graph
    graph_builder = StateGraph(AgentState)
    
    # Add nodes
    graph_builder.add_node("chatbot", chatbot)
    
    # Create the ToolNode with the tools list
    tool_node = ToolNode(TOOLS)
    graph_builder.add_node("tools", tool_node)
    
    # Set entry point
    graph_builder.set_entry_point("chatbot")
    
    # The `route_tools` function returns "tools" if the chatbot asks to use a tool, and "END" if
    # it is fine directly responding. This conditional routing defines the main agent loop.
    graph_builder.add_conditional_edges(
        "chatbot",
        route_tools,
        # The following dictionary lets you tell the graph to interpret the condition's outputs as a specific node
        {"tools": "tools", END: END},
    )
    
    # Any time a tool is called, we return to the chatbot to decide the next step
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_edge(START, "chatbot")
    
    # Compile the graph
    logger.info("Compiling graph")
    return graph_builder.compile()
