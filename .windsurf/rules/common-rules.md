---
trigger: always_on
---

Only two nodes for agent

Tools are from langchain.tools import tool

@tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers and return the result."""
    return a + b



from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

# ✅ ToolNode accepts tools defined with @tool
tools = [add_numbers]  # Could be dynamically discovered too
tool_node = ToolNode(tools)

# LangGraph state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Build graph
graph = StateGraph(AgentState)
graph.add_node("tools", tool_node)
graph.set_entry_point("tools")
graph.compile()

Generated scrips will have a unique name based on the llm context when script is saved 
no innovative changes should done without my permission
minumum changes to current code
always add meaningful debug logging
when ask to compare with a branch just do it and no innovative changes should done without my permission
have a good highlevel overview of the code
have a good highlevel overview of the change and the impact
break down the change into small steps
explain the change in detail
implement the changes incrementally and clarify with me 
when brainstom, do not jump into code examples first 
input_schema should be used to tool definition and not parameters

project objective is to build a self improving browser automation system that specializes in testing a specific web application by:
1. Starting with basic Playwright functions (click, fill, navigate)
2. Learning from user interactions to create reusable test functions
3. Save the interactions as scripts
4. Continuously improving test coverage and reliability

