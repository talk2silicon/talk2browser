"""
Browser Agent implementation using LangGraph for browser automation.

This module provides a stateful agent that can process natural language instructions
and execute browser automation tasks using Playwright.
"""
import os
import logging
import io
from typing import Annotated, Sequence, TypedDict, Optional
from PIL import Image  # For image compression

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
    navigate, click, fill, get_count, is_enabled, list_suggestions, generate_pdf_from_html,
    generate_script, generate_negative_tests, replay_action_json_with_playwright, list_files_in_folder,
    set_code_in_editor, save_json
)
from ..tools.script_tools import load_test_data
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
    list_suggestions,
    generate_pdf_from_html,
    generate_script,
    generate_negative_tests,
    replay_action_json_with_playwright,
    list_files_in_folder,
    load_test_data,
    set_code_in_editor,
    save_json  # <-- Added save_json tool for LLM
]
logger.debug(f"[Agent] TOOLS after registration: {[t.__name__ if hasattr(t, '__name__') else str(t) for t in TOOLS]}")
#logger.info(f"[Agent] TOOLS registered: {[t.__name__ if hasattr(t, '__name__') else str(t) for t in TOOLS]}")
def _tool_display_name(tool):
    return getattr(tool, 'name', None) or getattr(tool, '__name__', None) or type(tool).__name__
def log_registered_tools():
    tool_info = []
    for tool in TOOLS:
        name = _tool_display_name(tool)
        doc = getattr(tool, '__doc__', '')
        tool_info.append(f"- {name}: {doc.strip().splitlines()[0] if doc else 'No docstring'}")
    #logger.info("Registered tools (detailed):\n" + "\n".join(tool_info))

log_registered_tools()
#logger.info(f"Registered tools: [{', '.join(_tool_display_name(tool) for tool in TOOLS)}]")

# System prompt template
SYSTEM_PROMPT = """
You are a helpful AI assistant that can control a web browser to complete multi-step tasks.

## Vision-Based UI Element Detection:
- You may be provided with a section titled 'Vision UI Element Detections (YOLOv11)' containing a list of UI elements (with type, bounding box, and confidence) detected by a vision model from a screenshot of the current page.
- Use this information as additional context to help you reason about the UI, but always prefer the interactive elements hash map for tool calls.

## Search & Dropdown Handling:
- After filling a search field or typing into an input that triggers a dropdown or autocomplete, you MUST call the `list_suggestions` tool to enumerate all visible dropdown or autocomplete options.
- Always select/click the correct option (by label or intended value) from the suggestions using its stable hash before proceeding to the next step.
- Add debug logging after calling `list_suggestions` and after selection to record visible options and the selected value/hash.
- If no result appears, retry or suggest alternatives, and log all visible suggestions for debugging.
- If the target element for fill is not an <input>, <textarea>, <select>, or [contenteditable], do NOT use fill. Instead, click the element to open any associated widget (calendar, dropdown, etc.), then use list_suggestions or click/select the appropriate option. Log your reasoning and actions.

## Selector Format Requirements:
- All tools that accept selectors (navigate, click, fill, get_count, list_suggestions, etc.) REQUIRE CSS selectors, NOT XPath.
- CSS selectors use classes (.classname), IDs (#idname), and tag names (div, span) with combinators (>, +, ~).
- XPath selectors (like "html/body/div[1]/div[2]") will cause errors and should NOT be used.
- Valid CSS selector examples:
  - "#login-button" (element with ID "login-button")
  - ".product-item" (elements with class "product-item")
  - "article.trending-repo" (article elements with class "trending-repo")
  - "div > span" (span elements that are direct children of div elements)
  - "table tr:nth-child(2)" (second row in a table)
- If you need to target elements by their text content, use attribute selectors like: "button[text='Submit']" or "[aria-label='Search']"
- When using list_suggestions, provide a container selector (like "div.dropdown-menu") and optionally an item selector (like "li.option")

## Selector Format Guidelines:
- Use CSS selectors by default (e.g., "div.class", "#id", "[attribute=value]").
- For XPath selectors, always prefix with "xpath=" (e.g., "xpath=//div[@class='example']").
- Do not use raw XPath expressions without the "xpath=" prefix as this will cause parsing errors.
- When selecting by text content:
  - Prefer Playwright's text selector syntax: "text=Example Text" or "div >> text=Example"
  - Avoid jQuery-style ":contains()" syntax as it requires normalization
- For complex selections, consider using multiple simpler selectors in sequence rather than one complex selector.

## Script Generation Tool Usage:
- If the user requests a browser automation script (such as Playwright, Cypress, or Selenium), you MUST call the `generate_script` tool after completing all required browser actions.
- Infer the script type (Playwright, Cypress, Selenium) from the user's request. For example, if the user asks for a Playwright script, use `language='playwright'`; for a Selenium script, use `language='selenium'`; for a Cypress script, use `language='cypress'`.
- Do NOT simply list the steps or actions taken. You MUST call `generate_script` with the correct language argument as the final step.
- Do not mention or reference CLI commands, internal task names, or implementation details in your response or reasoning.
- Only call `generate_script` after all relevant actions have been performed and recorded.
- The output of `generate_script` is the path to the generated script file. Return this path to the user as the result of the script generation task.

## Sensitive Data Handling Policy:
- For any tool call that requires sensitive information (such as usernames, passwords, API keys, or any other secrets), always use the provided secret placeholder (e.g., ${company_password}) as the argument value.
- Never prompt the user for secret values, even if a secret is missing. Always assume that the agent or tool layer will handle secret resolution or user interaction.
- Do not mention secrets or placeholders in your output to the user.
- If a secret is missing, simply proceed as if the action was attempted, and do not ask the user for any sensitive information.

## File-based Test Data Injection:
- If the user mentions any file containing test data (e.g., "Use test data from ./data/login_data.json"), call the `load_test_data` tool with the provided file path.
- The file may be JSON, CSV, TXT, or any other text file. The tool will automatically parse JSON and return plain text for other types.
- Use the returned data as additional context for all subsequent tool calls and reasoning.
- If test data is provided both inline and via file, prefer the most recent or most complete data.
- If the file cannot be loaded, inform the user and proceed with what data is available.

## Core Capabilities:
- Web navigation (URLs, links, buttons, forms)
- Form filling and submission
- Content extraction and summarization
- Multi-step task execution
- Robust dropdown/autocomplete handling using `list_suggestions` and stable hashes
- PDF generation with complete content extraction

## Code Editor Automation:
- When you need to enter code into an online code editor (such as Ace, Monaco, or CodeMirror), use the set_code_in_editor tool instead of fill.
- set_code_in_editor accepts:
    - selector: The CSS selector for the editor container (e.g., .ace_editor, .monaco-editor)
    - code: The code string to inject into the editor
- Only use fill for standard <input>, <textarea>, or contenteditable fields.
- If you encounter an element that looks like a code editor (e.g., a <div> with code-like content or editor-specific classes) but is not an input/textarea/contenteditable, always try set_code_in_editor first, even if you are unsure of the editor type.
- If fill fails on a non-input element that appears to be a code editor, retry using set_code_in_editor.

Example:
- If asked to enter code into <input id="code-box">, use fill.
- If asked to enter code into <div class="monaco-editor"> or <div class="ace_editor">, use set_code_in_editor.
- If fill fails on a non-input element that appears to be a code editor, retry using set_code_in_editor.

## Guidelines:
1. When a full URL is provided, use page_goto to navigate directly to that URL
2. For search queries, prefer using DuckDuckGo (https://duckduckgo.com)
3. Prefer using the available tools for all browser actions
4. Only use the provided element hashes for element-related actions
5. Use the minimal number of steps to complete the task
6. Do not repeat actions unless necessary
7. For multi-step tasks, complete one step at a time and verify success before proceeding
8. Before generating a PDF, always extract all relevant details, including:
   - All subject details, tables, and related courses
   - Ensure the HTML/content to be converted to PDF is complete and not truncated
   - Add debug logging to verify the extracted content before PDF generation
9. If the target element for fill is not an <input>, <textarea>, <select>, or [contenteditable], do NOT use fill. Instead, click the element to open any associated widget (calendar, dropdown, etc.), then use list_suggestions or click/select the appropriate option. Log your reasoning and actions.
10. When asked to find and interact with elements, first analyze the page structure
11. If an action doesn't work as expected, try alternative approaches
12. Always verify the result of each action before proceeding to the next step

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
    # Optional vision meta-data for LLM context
    vision: dict

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
        #logger.info("BrowserAgent initialized with %s", self.llm.__class__.__name__)
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
            #logger.info("Creating initial BrowserPage and DOMService...")
            browser_page = BrowserPage(self.client.page)
            self.dom_service = browser_page.dom_service
            # Set DOMService reference for ActionService real-time merging
            ActionService.get_instance().set_dom_service(self.dom_service)
            # Expose mode change handler to Playwright (handled by ActionService)
            await ActionService.get_instance().expose_mode_change_handler(self.client.page)
            self.page_manager.add_page("main", browser_page)
            #logger.info("Initial BrowserPage added to PageManager as 'main'")

            # Initial scan for interactive elements
            #logger.info("Performing initial element scan on main BrowserPage...")
            await browser_page.dom_service.get_interactive_elements(highlight=True)
            elements_str, element_map = browser_page.dom_service.format_elements()
            #logger.info(f"Initial scan: {len(element_map)} elements mapped on 'main' page.")

            #logger.info("Browser, BrowserPage, and DOM service initialized successfully")
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
                logger.debug("Browser client closed successfully")
            except Exception as e:
                logger.warning("Error closing browser client: %s", str(e))
    
    def _create_agent_graph(self):
        """Create the two-node LangGraph for the agent, using the standard ToolNode."""
        logger.debug("Creating agent graph with standard ToolNode (no custom tool dispatch)")
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
            logger.debug(f"[Agent] _route_tools: tool_calls present in last message: {ai_message.tool_calls}")
            return "tools"
        logger.debug("[Agent] _route_tools: No tool calls in last message, ending conversation")
        return END

    # --- PageManager integration methods ---
    def create_new_page(self, page_id: str, playwright_page):
        """Create and add a new BrowserPage to the PageManager."""
        browser_page = BrowserPage(playwright_page)
        self.page_manager.add_page(page_id, browser_page)
        logger.debug(f"Created and added new BrowserPage with id {page_id}")

    def switch_page(self, page_id: str):
        """Switch to a different BrowserPage by id."""
        page = self.page_manager.switch_to(page_id)
        if page:
            logger.debug(f"Switched to BrowserPage with id {page_id}")
        else:
            logger.error(f"Failed to switch to BrowserPage with id {page_id}")

    def close_page(self, page_id: str):
        """Close and remove a BrowserPage by id."""
        self.page_manager.close_page(page_id)
        logger.debug(f"Closed BrowserPage with id {page_id}")
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
            logger.debug("Getting current page state")
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
                    logger.debug("Refreshing interactive elements...")
                    await dom_service.get_interactive_elements(highlight=True)

                    # Get formatted elements and map
                    elements_context, element_map = dom_service.format_elements()
                    logger.debug(f"Retrieved {len(element_map)} interactive elements")

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
            # --- Vision meta-data formatting and injection ---
            vision_section = ""
            screenshot_blobs = []
            import os, base64
            try:
                from ..services.vision_service import VisionService
                from ..utils.config import is_vision_enabled
                def format_vision_metadata(image_path, detections):
                    if not detections:
                        return "## Vision UI Element Detections (YOLOv11):\n(No UI elements detected by vision model.)"
                    lines = ["## Vision UI Element Detections (YOLOv11):"]
                    for d in detections:
                        label = d.get("label", "?")
                        bbox = d.get("bbox", [])
                        conf = d.get("confidence", 0)
                        lines.append(f"- [{label}] at {bbox}, confidence: {conf:.2f}")
                    if image_path:
                        lines.append(f"Screenshot: {image_path}")
                    return "\n".join(lines)
                # Attach screenshots to LLM vision input if feature flag enabled
                if os.getenv("T2B_SCREENSHOT_TO_LLM", "0") == "1":
                    logger.info("[Agent] Screenshot-to-LLM feature flag is enabled. Preparing screenshots for LLM vision input.")
                    agent_actions = ActionService.get_instance().get_agent_actions()
                    # Only include screenshots from recent actions (last 3, or all if fewer)
                    screenshots = [a.get("screenshot_path") for a in agent_actions[-3:] if a.get("screenshot_path")]
                    logger.debug(f"[Agent] Screenshots found for LLM input: {screenshots}")
                    for path in screenshots:
                        try:
                            # Add image compression to ensure size is under Claude's 5MB limit
                            with Image.open(path) as img:
                                # Start with quality 80 (good balance of quality and size)
                                quality = 80
                                max_size = 4.5 * 1024 * 1024  # 4.5MB to be safe (buffer below 5MB)
                                
                                # First try: compress with initial quality
                                compressed_img = io.BytesIO()
                                img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
                                
                                # Check if size is still too large
                                while compressed_img.tell() > max_size and quality > 15:
                                    # Reduce quality and try again
                                    quality -= 10
                                    logger.debug(f"[Agent] Reducing image quality to {quality} to meet size limit")
                                    compressed_img = io.BytesIO()
                                    img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
                                
                                # If still too large, resize the image
                                if compressed_img.tell() > max_size:
                                    # Calculate new dimensions to reduce by 25% each time
                                    width, height = img.size
                                    resize_factor = 0.75
                                    
                                    while compressed_img.tell() > max_size and resize_factor > 0.3:
                                        new_width = int(width * resize_factor)
                                        new_height = int(height * resize_factor)
                                        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                                        
                                        # Try with the resized image
                                        compressed_img = io.BytesIO()
                                        resized_img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
                                        
                                        # If still too large, reduce size further
                                        if compressed_img.tell() > max_size:
                                            resize_factor -= 0.15
                                        else:
                                            break
                                    
                                    logger.debug(f"[Agent] Resized image to {resize_factor:.2f}x original size to meet size limit")
                                
                                # Get the compressed image bytes
                                compressed_img.seek(0)
                                img_bytes = compressed_img.read()
                                
                                # Final size check - if still too large, use extreme measures
                                if len(img_bytes) > max_size:
                                    logger.warning(f"[Agent] Image still too large ({len(img_bytes)/1024/1024:.2f}MB), using grayscale conversion")
                                    gray_img = img.convert('L')  # Convert to grayscale
                                    compressed_img = io.BytesIO()
                                    gray_img.save(compressed_img, format="JPEG", quality=quality, optimize=True)
                                    compressed_img.seek(0)
                                    img_bytes = compressed_img.read()
                                
                                # Encode to base64
                                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                                screenshot_blobs.append(img_b64)
                                logger.info(f"[Agent] Added compressed screenshot {path} to LLM vision input (base64, {len(img_b64)} bytes, quality={quality})")
                        except Exception as e:
                            logger.error(f"[Agent] Failed to encode/compress screenshot {path} for LLM: {e}")
                if is_vision_enabled():
                    vision_results = VisionService.get_instance().get_latest_results()
                    vision_image = VisionService.get_instance().get_latest_image_path()
                    if vision_results and vision_image:
                        vision_section = format_vision_metadata(vision_image, vision_results)
                        state["vision"] = {"image_path": vision_image, "detections": vision_results}
                        logger.info(f"[Agent] Added vision data to state: {state['vision']}")
                    else:
                        logger.info("[Agent] Vision enabled but no results to add to state.")
            except Exception as e:
                logger.error(f"[Agent] Vision meta-data formatting/injection failed: {e}")
            # Create system message content
            system_content = "\n\n".join([
                SYSTEM_PROMPT,
                "Current page state:",
                "\n".join(context),
                element_map_str,
                vision_section
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

            # --- LLM Debug Logging ---
            logger.debug(f"[Agent] Registered tools: {[t.name if hasattr(t, 'name') else t.__name__ for t in TOOLS]}")
            logger.debug(f"[Agent] LLM input messages (system+user):\n{[getattr(m, 'content', str(m)) for m in messages]}")
            logger.debug(f"[Agent] System prompt (truncated to 500 chars): {system_content[:500]}")
            # Prepare LLM with tools
            llm_with_tools = self.llm.bind_tools(TOOLS)
            # Attach screenshots as image blocks in HumanMessage if feature flag is enabled
            if os.getenv("T2B_SCREENSHOT_TO_LLM", "0") == "1" and screenshot_blobs:
                logger.info("[Agent] Attaching screenshots to LLM input as image blocks in message content")
                # Find the last HumanMessage (the user prompt)
                from langchain_core.messages import HumanMessage
                for i in range(len(messages)-1, -1, -1):
                    if isinstance(messages[i], HumanMessage):
                        user_msg = messages[i]
                        break
                else:
                    user_msg = None
                if user_msg and isinstance(user_msg.content, str):
                    # Replace string content with a list of content blocks
                    content_blocks = [{"type": "text", "text": user_msg.content}]
                    for blob in screenshot_blobs:
                        logger.debug(f"[Agent] Screenshot blob type: {type(blob)}, length: {len(blob) if isinstance(blob, str) else 'N/A'}")
                        if isinstance(blob, str) and blob.strip():
                            content_blocks.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": blob
                                }
                            })
                        else:
                            logger.error(f"[Agent] Skipping invalid screenshot blob: {blob}")
                    logger.debug(f"[Agent] LLM HumanMessage content blocks: {content_blocks}")
                    messages[i] = HumanMessage(content=content_blocks)
            
            # Invoke LLM with tools
            response = await llm_with_tools.ainvoke(messages)
            logger.debug(f"[Agent] LLM response: {response}")
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"[Agent] LLM tool calls: {response.tool_calls}")
            if self.info_mode and hasattr(response, 'tool_calls') and response.tool_calls:
                tools_used = [call['name'] if isinstance(call, dict) else getattr(call, 'name', str(call)) for call in response.tool_calls]
                step = f"Step: LLM decided to use tool(s): {', '.join(tools_used)}"
                print(step)
                self.story_log.append(step)
            
            # Check if response has tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info("Tool calls detected in LLM response")
                # --- Calendar Trigger Post-Processing ---
                try:
                    # Only process if the last tool call is a click
                    last_tool_call = response.tool_calls[-1] if response.tool_calls else None
                    if last_tool_call and (getattr(last_tool_call, 'name', None) == 'click' or (isinstance(last_tool_call, dict) and last_tool_call.get('name') == 'click')):
                        # Try to extract selector/label for calendar detection
                        args = getattr(last_tool_call, 'args', None) or last_tool_call.get('args', {})
                        selector = args.get('selector', '') if args else ''
                        # Heuristic: look for calendar triggers by selector or label
                        calendar_keywords = ['calendar', 'date', 'check in', 'check out', 'add dates']
                        if any(k in selector.lower() for k in calendar_keywords):
                            #logger.info(f"[Calendar Hook] Detected calendar trigger click: {selector}. Will wait for popup...")
                            # Wait for a likely calendar popup (heuristic selector)
                            popup_selectors = ['[role="dialog"]', '.calendar', '.datepicker', '[data-testid*="calendar"]', '[aria-label*="calendar"]']
                            from ..tools.browser_tools import wait_for_selector
                            found_popup = False
                            for popup_selector in popup_selectors:
                                #logger.info(f"[Calendar Hook] Waiting for popup selector: {popup_selector}")
                                result = await wait_for_selector(popup_selector, state="visible", timeout=4000)
                                #logger.info(f"[Calendar Hook] wait_for_selector result for {popup_selector}: {result}")
                                if 'Waited' in result:
                                    found_popup = True
                                    break
                            if not found_popup:
                                logger.warning(f"[Calendar Hook] No calendar popup appeared after click on {selector}")
                            else:
                                # Refresh DOM after popup appears
                                browser_page = PageManager.get_instance().get_current_page()
                                dom_service = browser_page.get_dom_service() if browser_page else None
                                if dom_service:
                                    #logger.info("[Calendar Hook] Refreshing interactive elements after calendar popup...")
                                    await dom_service.get_interactive_elements(highlight=True)
                                    #logger.info("[Calendar Hook] DOM refreshed after calendar popup.")
                except Exception as cal_exc:
                    logger.error(f"[Calendar Hook] Error in calendar post-processing: {cal_exc}", exc_info=True)
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
            result = await self.graph.ainvoke(initial_state, config={"recursion_limit": 100})
            # Get final response
            messages = result["messages"]
            last_message = messages[-1]
            # Extract content from last message
            response = last_message.content if hasattr(last_message, 'content') else str(last_message)
            logger.info("Agent task completed")
            # --- Final block: generate and save merged action JSON with scenario_name ---
            try:
                path = ActionService.get_instance().save_merged_actions_with_prompt(task)
                #logger.info(f"Merged actions saved to {path} via ActionService.save_merged_actions_with_prompt")
            except Exception as final_exc:
                logger.error(f"Failed to save merged actions: {final_exc}")
            # --- End final block ---
            return response
        except Exception as e:
            error_msg = f"Error running agent: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
