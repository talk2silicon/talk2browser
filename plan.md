# Project Plan: Playwright Script Generation, DOM Highlighting, and Sensitive Data Handling

## Objective
Build a self-improving browser automation system for testing a specific web application, starting with Playwright functions (click, fill, navigate), learning from user interactions, saving scripts, and continuously improving test coverage and reliability.

## Recent Context
- **Element highlighting refactor:** Only dashed border for all interactive elements (LLM context) remains. All explicit Playwright action highlight logic (blue border) has been removed from both JS and Python. The browser now relies on native browser/site focus/active cues for actions.
- **Removed:** `.t2b-element-highlight-active` CSS, `highlight_element_for_action`, and `clear_element_action_highlight` from DOMService and all tool functions.
- **Preserved:** `.t2b-element-highlight` for context highlighting (dashed border), with no background override (original element colors preserved).
- **Current plan and task list updated for continuity after IDE restart.**
- **Selenium script generation and agent debugging plan saved for future reference.**

## Current Working Plan
### Browser Automation Refactor Plan

#### Notes
- Each browser page (tab/window/popup) is represented by a `BrowserPage` object.
- Each `BrowserPage` has its own `DOMService` instance (no singleton/global DOM state).
- `PageManager` tracks all open `BrowserPage` objects and manages which is currently active. Implemented as a singleton with `get_instance()`.
- All browser tools should interact with the Playwright page and DOM service via the `BrowserPage` abstraction, fetched from `PageManager.get_instance().get_current_page()`.
- Naming aligns with Playwright conventions for clarity and maintainability.
- Debug logging and test coverage must be maintained throughout the refactor.
- `anthropic._base_client` logging set to WARNING to reduce noise.
- `tools/__init__.py` synchronized with available tools in `tools/browser_tools.py`.
- DOM element hash map logic encapsulated within `DOMService`.
- Agent's `custom_tool_dispatch_node` removed (using standard `ToolNode`).
- Conditional routing from the 'agent' node (chatbot) to 'tools' or `END` uses `add_conditional_edges`.
- LLM cannot pass Python objects (like `BrowserPage`) to tools; tools must fetch `BrowserPage` internally if needed.
- Duplicate `PageManager` definition in `browser/page_manager.py` removed.
- Scripts run as modules (e.g., `python -m examples.test_agent`) for consistent import contexts.
- Playwright's `locator()` expects XPath selectors to be prefixed with `xpath=`.
- `buildDomTree.js` uses only class-based highlighting for interactive elements.
- Python lint errors in `browser_tools.py` (empty try blocks) fixed.
- Highlighting logic in tools like `fill`, `click` refactored to remove explicit action highlight.
- Debug logging added for tool calls and important state changes.

#### Task List
- [x] Refactor or define `DOMService` to be per-page (no global state).
- [x] Implement `BrowserPage` abstraction and update browser tool functions.
- [x] Implement `PageManager` singleton.
- [x] Update agent logic for page management.
- [x] Add debug logging.
- [x] Update `tools/__init__.py`.
- [x] Remove `get_all_elements` tool.
- [x] Fix Playwright locator usage for XPath selectors.
- [x] Refactor agent's internal DOM service handling.
- [x] Remove duplicate `PageManager` definition.
- [x] Fix hash resolution errors.
- [x] Fix Playwright locator usage and `NameError` in `click` tool.
- [x] Refactor duplicated error handling logic in browser tools.
- [x] Remove all explicit Playwright action highlight logic (blue border) from JS and Python.
- [x] Remove `.t2b-element-highlight-active` CSS and related JS logic.
- [x] Remove `highlight_element_for_action` and `clear_element_action_highlight` from DOMService.
- [x] Remove calls to those methods from browser tool functions.
- [x] Update `clearHighlights` to only remove `.t2b-element-highlight`.
- [x] Confirm only LLM context highlight (dashed border) remains.
- [ ] Verify overall element highlighting and proceed with remaining tasks.

## Current Goal
- Keep only dashed border highlight for all interactive elements (LLM context).
- Remove all explicit Playwright action highlight logic (blue border) from both JS and Python.
- Save this context and plan for continuity after IDE restart.


## Objective
Debug, enhance, and stabilize Playwright script generation within the talk2browser project by implementing a robust ActionRecorder, adding missing atomic Playwright browser tools for advanced e-commerce automation, ensuring unique timestamped filenames for generated scripts, and securely handling sensitive data by substituting placeholders with real values only at execution time, while restricting browser navigation to allowed domains and preventing sensitive data exposure to the LLM.

## Current Working Plan
### Playwright Script Generation from Browser Actions

#### Notes
- Fixed DOM highlighting: now only calls global JS functions from buildDomTree.js, no dynamic inline JS in service.py.
- Confirmed no other dynamic JS function definitions in dom/service.py; all complex DOM logic centralized in JS file.
- Fixed Playwright evaluate usage to use a single argument dict and lambda-style destructuring.
- New: Instead of adding recording logic to BrowserTools, introduce a dedicated action recorder/registry class for minimal changes and better separation of concerns.
- New: In the final block of agent execution, generate both the Playwright script and the JSON action log into the ./generated folder.
- ActionRecorder class implemented, integrated with browser tool calls and agent final block.
- Issue: Generated Playwright script not found after agent run (possible path, permissions, or error in script generation).
- Issue: Click action on '#add-to-cart-sauce-labs-backpack' fails with Playwright timeout (element not visible or selector issue).
- New: Add debug output to print all interactive elements with their hash and values before click attempts, to aid troubleshooting selector/click issues.
- New: Hashes are being used directly as selectors in click actions, causing Playwright syntax errors (hashes are not valid selectors for querySelectorAll).
- Fixed: Hashes are now transparently resolved to selectors in click actions using DOMService, preventing invalid selector errors.
- Enhancement planned: Playwright scripts should be saved with unique names including a timestamp and part of the prompt, to avoid overwriting and improve traceability.
- Implemented: Playwright scripts are now saved with unique names (timestamp + prompt snippet) for every run, improving traceability and preventing overwrites.
- Added: New Playwright atomic tools (`get_all_elements`, `is_enabled`, `get_count`) for advanced e-commerce flows. Screenshot tool intentionally omitted as per user instruction.

#### Task List
- [x] Debug and refactor DOM highlighting to use only JS file methods
- [x] Fix Playwright evaluate argument usage in Python
- [x] Implement ActionRecorder/Registry class to collect tool actions
- [x] Integrate ActionRecorder with browser tool calls
- [x] Implement Playwright script and JSON log generation in final block of agent
- [x] Test and validate generated Playwright scripts and action logs
  - [x] Debug missing generated Playwright script output in ./generated
  - [x] Investigate and resolve click timeout on '#add-to-cart-sauce-labs-backpack'
    - [x] Print interactive elements with hash and values for debugging in click tool
    - [x] Fix bug: hashes must be resolved to selectors before click (do not use hashes directly as selectors)
- [x] Implement unique script naming: include timestamp and prompt snippet in generated Playwright script filenames
- [x] Expand browser tools to support complex e-commerce flows (Migros Online prompt): advanced search, multi-item add, basket management, dynamic alternative selection, delivery slot selection, checkout with payment method, etc.
- [ ] Test and validate new Playwright tools (`get_all_elements`, `is_enabled`, `get_count`) with Migros grocery prompt

#### Current Goal
- Test and validate new Playwright tools for Migros grocery prompt

## Next Steps
1. Implement Sensitive Data Handling:
   - Refactor the agent and tools to accept a `sensitive_data` map of placeholder to real values keyed by domain.
   - Substitute placeholders with real sensitive values only at the Playwright tool execution layer.
   - Ensure LLM and logs only see placeholders, never real secrets.
2. Implement Browser Domain Restrictions:
   - Add support for restricting browser navigation to a whitelist of allowed domains.
   - Prevent the agent from visiting untrusted URLs.
3. Disable Vision/Screenshots for Sensitive Data:
   - Optionally disable or redact screenshots when sensitive data is involved to avoid data leakage.
4. Test and Validate:
   - Thoroughly test the new atomic Playwright tools (`get_all_elements`, `is_enabled`, `get_count`) with the Migros grocery prompt.
   - Test sensitive data substitution and domain restrictions once implemented.
5. Further Refactor and Hardening:
   - Continue improving code maintainability, error handling, and logging.
   - Possibly add more atomic Playwright tools as needed by the grocery automation scenario.

## Design Decisions
- Use a dedicated `ActionRecorder` singleton to record all browser tool actions and generate reproducible Playwright scripts and JSON logs.
- Generate unique Playwright script filenames combining timestamp and a sanitized snippet of the user prompt for better traceability.
- Add granular Playwright tools that map one-to-one to Playwright API calls, avoiding high-level composite or "smart" tools.
- Use a decorator `resolve_hash_args` to transparently convert element hash selectors to valid CSS selectors before Playwright actions.
- Avoid exposing sensitive data (e.g., passwords, tokens) to the LLM by using placeholders in prompts and substituting real values only at the browser interaction layer (planned next step).
- Restrict browser navigation to allowed domains for security (planned next step).
- Disable vision or screenshot capture when sensitive data is involved to prevent accidental exposure (planned next step).

## Security Preferences
- Handle sensitive data securely by:
  - Using placeholders in the prompt/task visible to the LLM.
  - Substituting real sensitive values only at the Playwright tool execution layer.
  - Optionally restricting browser navigation to whitelisted domains.
  - Disabling vision or screenshot capture when sensitive data is involved.

## User Preferences
- Only add Playwright atomic tools (direct wrappers for Playwright API calls), no composite or high-level tools.
- Do not add screenshot tools currently.
- Use relative imports to avoid `ModuleNotFoundError`.
- Use detailed debug logging and error handling for all browser tools.
- Use timestamped unique filenames for generated Playwright scripts.
- Restore accidentally deleted files and revert changes via git as needed.
- Prepare for next steps to implement sensitive data handling and browser domain restrictions.

## Blockers and Bugs
- Initial failure to find the generated Playwright script due to import errors and path issues (resolved).
- Playwright click failures caused by passing element hashes directly as selectors (resolved by hash resolution decorator).
- Timeout and click failures on specific selectors like `#add-to-cart-sauce-labs-backpack` (debugging aided by new tools).
- User accidentally deleted `examples/test_agent.py` (restored and reverted successfully).
- User encountered a file-not-found error when running the test agent script due to the missing test file (resolved).
