always scan the existing code in more details 
Only two nodes for agent
sklern for tool filtering
dynamic playwright tool registration
generated scrips also act as tools for subsequent runs
generated scrips will have a unique name based on the llm context when script is saved 
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

After implementing these changes, here's the flow of operations:

Initial Request Flow
CopyInsert
User Request
  │
  ▼
BrowserAgent.run()
  │
  ▼
Initial State Creation
{messages: [HumanMessage(task)]}
  │
  ▼
Graph Entry Point ("agent")
Chatbot Node Flow (_chatbot)
CopyInsert
Get Page State & Elements
  │
  ▼
Format System Message
  │  - Current URL
  │  - Page Title
  │  - Interactive Elements (#hashes)
  │
  ▼
Prepare Conversation
  │  - System Message
  │  - User Messages
  │  - Previous Tool Results
  │
  ▼
LLM Invocation
  │  - Claude API Call
  │  - Tools Bound via ToolNode
  │
  ▼
Route Decision
  │
  ├─► If tool_calls: return "tools"
  └─► If no tool_calls: return END
Tools Node Flow
CopyInsert
ToolNode (LangGraph Built-in)
  │
  ▼
Extract Tool Calls
  │
  ▼
For Each Tool Call:
  │  1. Resolve #hash to XPath
  │  2. Execute Browser Action
  │  3. Capture Result
  │
  ▼
Return to "agent" Node
State Updates
CopyInsert
Messages State
  │
  ├─► System Message (Context)
  ├─► User Messages
  ├─► Tool Results
  └─► AI Responses

Graph Routing
  │
  ├─► "agent" → "tools" (when tools needed)
  ├─► "tools" → "agent" (after execution)
  └─► "agent" → END (when complete)
Error Handling Flow
CopyInsert
Error Detection
  │
  ├─► Claude API Errors
  ├─► Browser Action Errors
  └─► State Management Errors
  │
  ▼
Error Response
  │
  ├─► Log Error Details
  ├─► Add Error Message to State
  └─► Return Helpful Message
Example Interaction Flow
CopyInsert
User: "Click the login button"
  │
  ▼
1. Chatbot Node
   - Gets page state
   - Finds interactive elements
   - Sees: #abc123 - button [text="Login"]
   - LLM decides to use click tool
  │
  ▼
2. Tools Node
   - Resolves #abc123 to XPath
   - Executes click
   - Returns result
  │
  ▼
3. Back to Chatbot Node
   - Updates context with new page state
   - Gets new interactive elements
   - Ready for next instruction
Debug Logging Flow
CopyInsert
Each Step Logged
  │
  ├─► Page State Changes
  ├─► Element Discovery
  ├─► Tool Executions
  ├─► State Transitions
  └─► Error Conditions