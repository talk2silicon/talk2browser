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
# ManualModeService fully merged into ActionService; import not needed.
from ..browser.page import BrowserPage
from ..browser.page_manager import PageManager
from ..tools import (
    navigate, click, fill, get_count, is_enabled, list_interactive_elements, generate_pdf_from_html,
    generate_script, generate_negative_tests, replay_action_json_with_playwright, list_files_in_folder
)
from ..services.action_service import ActionService  # Ensure this is at the top
from ..services.sensitive_data_service import SensitiveDataService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Suppress noisy HTTP request/response logs from Anthropic client
logging.getLogger("anthropic._base_client").setLevel(logging.WARNING)

# Define available tools for the agent
TOOLS = [
    navigate,
    click,
    fill,
    get_count,
    is_enabled,
    list_interactive_elements,
    generate_pdf_from_html,
    generate_script,
    generate_negative_tests,
    replay_action_json_with_playwright,
    list_files_in_folder
]
def _tool_display_name(tool):
    return getattr(tool, 'name', None) or getattr(tool, '__name__', None) or type(tool).__name__
def log_registered_tools():
    tool_info = []
    for tool in TOOLS:
        name = _tool_display_name(tool)
        doc = getattr(tool, '__doc__', '')
        tool_info.append(f"- {name}: {doc.strip().splitlines()[0] if doc else 'No docstring'}")
    logger.info("Registered tools (detailed):\n" + "\n".join(tool_info))

log_registered_tools()
logger.info(f"Registered tools: [{', '.join(_tool_display_name(tool) for tool in TOOLS)}]")

# System prompt template
# SYSTEM_PROMPT updated: Explicitly instructs LLM to call generate_script after navigation if the task is script generation or only navigation actions are present.
SYSTEM_PROMPT = """You are a helpful AI assistant that can control a web browser to complete multi-step tasks.

## Sensitive Data Handling Policy:
- For any tool call that requires sensitive information (such as usernames, passwords, API keys, or any other secrets), always use the provided secret placeholder (e.g., ${company_password}) as the argument value.
- Never prompt the user for secret values, even if a secret is missing. Always assume that the agent or tool layer will handle secret resolution or user interaction.
- Do not mention secrets or placeholders in your output to the user.
- If a secret is missing, simply proceed as if the action was attempted, and do not ask the user for any sensitive information.

## Core Capabilities:
- Web navigation (URLs, links, buttons, forms)
- Form filling and submission
- Content extraction and summarization
- Multi-step task execution

## Guidelines:
1. When a full URL is provided, use page_goto to navigate directly to that URL
2. For search queries, prefer using DuckDuckGo (https://duckduckgo.com)
3. Prefer using the available tools for all browser actions
4. Only use the provided element hashes for element-related actions
5. Use the minimal number of steps to complete the task
6. Do not repeat actions unless necessary
7. For multi-step tasks, complete one step at a time and verify success before proceeding
8. When asked to find and interact with elements, first analyze the page structure
9. If an action doesn't work as expected, try alternative approaches
10. Always verify the result of each action before proceeding to the next step

## Script Generation Guidance:
- If the user task involves generating a script (e.g., Playwright, Selenium, Cypress), and you have completed the necessary navigation and exploration steps, call the generate_script tool with the recorded actions.
- If only navigation actions are present and the task is to generate a script, call generate_script immediately after navigation.
- Do NOT loop or repeat navigation or element scanning if the task is script generation and actions are already recorded.

## Multi-step Navigation:
- Clearly identify each step before executing it
- Verify the success of each step before proceeding
- If a step fails, analyze why and try an alternative approach
- Maintain context between steps to ensure continuity

## Error Handling:
- If an element is not found, check for iframes, modals, or dynamic content
- If a page doesn't load, try refreshing or going back and retrying
- If stuck, analyze the page structure and try a different approach

## Action Replay Strictness:
- When the user requests to replay an action JSON file, ONLY call the replay tool. If the replay fails, report the error and do not attempt to generate scripts or take additional actions unless the user explicitly requests them.
"""

class AgentState(TypedDict):
    """State for the browser agent following LangGraph pattern."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str  # For LangGraph routing

class BrowserAgent:
    """Agent for browser automation using LangGraph and Playwright."""
    
    def __init__(self, llm: Optional[ChatAnthropic] = None, headless: bool = False, info_mode: bool = False, sensitive_data: dict = None):
        """Initialize the browser agent.
        
        Args:
            llm: Optional ChatAnthropic instance. If not provided, a default one will be created.
            headless: Whether to run the browser in headless mode.
            info_mode: If True, print live story-mode logs (step-by-step narrative)
            sensitive_data: Optional dict of secret keys/values for runtime secret injection
        """
        self.headless = headless
        self.info_mode = info_mode
        self.sensitive_data = sensitive_data or {}
        self.story_log = []  # Collects story steps if info_mode is enabled
        # Initialize LLM
        self.llm = llm or ChatAnthropic(
            model=os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307"),
            temperature=0.0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        from .llm_singleton import set_llm
        set_llm(self.llm)
        
        # Initialize browser client and DOM service (will be started in __aenter__)
        self.client = PlaywrightClient(headless=headless)
        self.dom_service = None
        # ManualModeService fully merged into ActionService; no instance needed.
        # Initialize PageManager (singleton)
        self.page_manager = PageManager.get_instance()
        
        # User-friendly SensitiveDataService auto-init
        if getattr(SensitiveDataService, "_instance", None) is None:
            logger.warning("SensitiveDataService not configured, defaulting to environment-only secrets.")
            SensitiveDataService.configure({})
        
        self.graph = self._create_agent_graph()
        logger.info("BrowserAgent initialized with %s", self.llm.__class__.__name__)
        logger.debug(f"Sensitive data keys: {list(self.sensitive_data.keys()) if self.sensitive_data else []}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        try:
            # Start the browser
            logger.debug("Starting browser...")
            await self.client.start()
            if not self.client.page:
                raise RuntimeError("Failed to create browser page")
            await self.client.page.wait_for_load_state("domcontentloaded")
            await self.client.page.wait_for_load_state("networkidle")

            # Create BrowserPage abstraction and add to PageManager
            logger.info("Creating initial BrowserPage and DOMService...")
            browser_page = BrowserPage(self.client.page)
            self.dom_service = browser_page.dom_service
            # Set DOMService reference for ActionService real-time merging
            ActionService.get_instance().set_dom_service(self.dom_service)
            # Expose mode change handler to Playwright (handled by ActionService)
            await ActionService.get_instance().expose_mode_change_handler(self.client.page)
            self.page_manager.add_page("main", browser_page)
            logger.info("Initial BrowserPage added to PageManager as 'main'")

            # Initial scan for interactive elements
            logger.info("Performing initial element scan on main BrowserPage...")
            await browser_page.dom_service.get_interactive_elements(highlight=True)
            elements_str, element_map = browser_page.dom_service.format_elements()
            logger.info(f"Initial scan: {len(element_map)} elements mapped on 'main' page.")

            logger.info("Browser, BrowserPage, and DOM service initialized successfully")
            return self
        except Exception as e:
            logger.error("Failed to initialize browser: %s", str(e), exc_info=True)
            await self.__aexit__(type(e), e, None)
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
        """Create the two-node LangGraph for the agent, using the standard ToolNode."""
        logger.info("Creating agent graph with standard ToolNode (no custom tool dispatch)")
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._chatbot)
        workflow.add_node("tools", ToolNode(TOOLS))
        # Conditional routing: if _route_tools returns "tools", go to tools, else END
        workflow.add_conditional_edges(
            "agent",
            self._route_tools,
            {"tools": "tools", END: END}
        )
        workflow.add_edge("tools", "agent")
        workflow.set_entry_point("agent")
        self.graph = workflow.compile()
        logger.debug("Created agent graph with standard ToolNode and conditional routing")
        return self.graph


    
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
        MAX_TOOL_CALLS = 50
        if tool_call_count >= MAX_TOOL_CALLS:
            logger.warning(f"Reached maximum tool calls ({MAX_TOOL_CALLS}), ending conversation")
            return END
        
        # Check if the last message has tool calls
        if hasattr(ai_message, "tool_calls") and ai_message.tool_calls:
            return "tools"
        
        # No tool calls
        return END

    # --- PageManager integration methods ---
    def create_new_page(self, page_id: str, playwright_page):
        """Create and add a new BrowserPage to the PageManager."""
        browser_page = BrowserPage(playwright_page)
        self.page_manager.add_page(page_id, browser_page)
        logger.info(f"Created and added new BrowserPage with id {page_id}")

    def switch_page(self, page_id: str):
        """Switch to a different BrowserPage by id."""
        page = self.page_manager.switch_to(page_id)
        if page:
            logger.info(f"Switched to BrowserPage with id {page_id}")
        else:
            logger.error(f"Failed to switch to BrowserPage with id {page_id}")

    def close_page(self, page_id: str):
        """Close and remove a BrowserPage by id."""
        self.page_manager.close_page(page_id)
        logger.info(f"Closed BrowserPage with id {page_id}")
    # --- End PageManager integration ---

    
    async def _chatbot(self, state: AgentState) -> AgentState:
        """Process messages with LLM and determine next step with full context.
        Handles page state, interactive elements, and LLM interaction.
        """
        logger.info("[Agent] Waiting for manual mode if needed...")
        await ActionService.get_instance().wait_if_manual_mode()
        logger.info("[Agent] Manual mode wait complete. Checking for new manual actions...")

        # Only inject new manual actions (one-time) after each manual mode pause
        new_manual_actions = ActionService.get_instance().pop_new_manual_actions()
        logger.info(f"[Agent] Retrieved {len(new_manual_actions)} new manual actions after manual mode pause.")
        logger.debug(f"[Agent] Message state before manual action injection: {state['messages']}")
        if new_manual_actions:
            from langchain_core.messages import ToolMessage
            logger.info(f"[Agent] Injecting {len(new_manual_actions)} new manual actions into LLM context.")
            for action in new_manual_actions:
                msg = ToolMessage(
                    tool_call_id=action.get("id", "manual"),
                    tool_name=action.get("type", "manual_action"),
                    content=str(action)
                )
                state["messages"].append(msg)
            logger.debug(f"[Agent] Message state after manual action injection: {state['messages']}")
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

            # Always fetch the current DOM service from the current page (singleton)
            from ..browser.page_manager import PageManager
            browser_page = PageManager.get_instance().get_current_page()
            dom_service = browser_page.get_dom_service() if browser_page else None

            if dom_service:
                try:
                    # Refresh interactive elements
                    logger.info("Refreshing interactive elements...")
                    await dom_service.get_interactive_elements(highlight=True)

                    # Get formatted elements and map
                    elements_context, element_map = dom_service.format_elements()
                    logger.info(f"Retrieved {len(element_map)} interactive elements")

                    # Overwrite element map in state for tools (removes any previous map)
                    state["element_map"] = element_map  # Always latest
                    logger.debug(f"[Agent] Overwrote element_map in state with {len(element_map)} elements")

                    if self.info_mode:
                        step = f"Step: Inspected the page for interactive elements.\n  → Found elements:\n{elements_context}"
                        print(step)
                        self.story_log.append(step)
                except Exception as e:
                    logger.error(f"Error getting interactive elements: {e}", exc_info=True)
                    elements_context = f"Error scanning elements: {str(e)}"
                    if self.info_mode:
                        step = f"Step: Failed to scan elements due to error: {str(e)}"
                        print(step)
                        self.story_log.append(step)
            else:
                logger.warning("No DOM service available")
                elements_context = "DOM service not initialized"
                if self.info_mode:
                    step = "Step: DOM service not initialized. Skipping element scan."
                    print(step)
                    self.story_log.append(step)
            
            # Build context for LLM
            context = [
                f"Current URL: {current_url}",
                f"Page title: {current_title}",
                elements_context
            ]
            # Build a human-readable element hash map section
            if element_map:
                element_map_section = ["\n## Interactive Elements (hash → description):"]
                for h, desc in element_map.items():
                    element_map_section.append(f"- {h}: {desc}")
                element_map_section.append("\n**Only use these hashes in your tool calls.**")
                element_map_str = "\n".join(element_map_section)
            else:
                element_map_str = "\n(No interactive elements detected on this page.)"
            # Create system message content
            system_content = "\n\n".join([
                SYSTEM_PROMPT,
                "Current page state:",
                "\n".join(context),
                element_map_str
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
            # Log full messages sent to LLM
            logger.debug(f"[Agent] LLM input messages: {[str(m) for m in messages]}")
            response = await llm_with_tools.ainvoke(messages)
            logger.debug(f"[Agent] LLM response: {response}")
            # If response has tool_calls, log them
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"[Agent] LLM tool calls: {response.tool_calls}")
            
            # Info mode: log tool selection step
            if self.info_mode and hasattr(response, 'tool_calls') and response.tool_calls:
                tools_used = [call['name'] if isinstance(call, dict) else getattr(call, 'name', str(call)) for call in response.tool_calls]
                step = f"Step: LLM decided to use tool(s): {', '.join(tools_used)}"
                print(step)
                self.story_log.append(step)
            
            # Check if response has tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info("Tool calls detected in LLM response")
                return {
                    "messages": messages + [response],
                    "next": "tools"
                }
            
            # No tool calls, end the conversation
            logger.info("No tool calls in LLM response, ending conversation")
            if self.info_mode:
                step = "Step: No further tool actions needed. Conversation ending."
                print(step)
                self.story_log.append(step)
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
    
    async def run(self, task: str, sensitive_data: dict = None) -> str:
        """Run the agent with the given task.
        
        Args:
            task: The task or query for the agent.
            sensitive_data: Optional dict for runtime secret injection (overrides self.sensitive_data)
        Returns:
            The agent's response as a string.
        """
        try:
            # Use provided sensitive_data or fall back to self.sensitive_data
            effective_sensitive_data = sensitive_data or self.sensitive_data or {}
            # Configure SensitiveDataService for this run
            from talk2browser.services.sensitive_data_service import SensitiveDataService
            SensitiveDataService.configure(effective_sensitive_data)
            logger.info(f"SensitiveDataService configured with keys: {list(effective_sensitive_data.keys()) if effective_sensitive_data else []}")
            # Initialize state
            initial_state = AgentState(
                messages=[HumanMessage(content=task)],
                next="agent"
            )
            logger.info(f"Starting agent with task: {task}")
            result = await self.graph.ainvoke(initial_state)
            # Get final response
            messages = result["messages"]
            last_message = messages[-1]
            # Extract content from last message
            response = last_message.content if hasattr(last_message, 'content') else str(last_message)
            logger.info("Agent task completed")
            # --- Final block: generate and save merged action JSON with scenario_name ---
            try:
                import os
                import re
                os.makedirs("./generated", exist_ok=True)
                scenario_name = re.sub(r'[^a-zA-Z0-9_]', '_', task.lower().split()[0]) if task else "scenario"
                merged_path = f"./generated/merged_actions_{scenario_name}.json"
                merged_actions = ActionService.get_instance().actions
                from ..tools.file_system_tools import save_json_to_file
                save_json_to_file(merged_path, merged_actions)
                logger.info(f"Merged actions saved to {merged_path} via save_json_to_file (using ActionService singleton)")
            except Exception as final_exc:
                logger.error(f"Failed to save merged actions: {final_exc}")
            # --- End final block ---
            return response
        except Exception as e:
            error_msg = f"Error running agent: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
