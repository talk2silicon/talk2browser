# Project Design & Architecture

## 1. Overall Architecture

This project is a modular, agent-driven browser automation framework built on Playwright, with a strong separation of concerns between agent logic, browser interaction, DOM state management, tool interfaces, and service layers.

### Key Architectural Layers:

- **Agent Layer** (`src/talk2browser/agent/`):  
  Orchestrates high-level workflows, LLM integration, and tool invocation. The main entry point is likely `agent.py` with the `BrowserAgent` class, which manages the lifecycle of an automation session, delegates tool calls, and records actions.

- **Browser Layer** (`src/talk2browser/browser/`):  
  Encapsulates all direct browser interactions.  
  - `page.py` and `page_manager.py` manage browser pages/tabs.
  - `dom/` submodule contains the canonical `DOMService` (in `dom/service.py`), which is responsible for DOM scanning, element mapping, and element-level actions (click, type, highlight, etc.).

- **Tools Layer** (`src/talk2browser/tools/`):  
  Exposes browser and system capabilities as LLM-callable tools.  
  - `browser_tools.py` is the main entry point for browser actions (navigate, click, fill, screenshot, etc.), and acts as a bridge between the agent/LLM and the browser/service layers.
  - Other files expose custom, file system, and script tools.

- **Services Layer** (`src/talk2browser/services/`):  
  Implements cross-cutting concerns and singleton services:
  - `action_service.py`: Tracks and manages all recorded actions (manual and agent-driven), supporting replay, audit, and reporting.
  - `script_generation_service.py`: Handles code/script generation from action logs.
  - `sensitive_data_service.py`: Securely manages secrets and sensitive data.
  - `vision_service.py`: (If enabled) Handles vision/YOLO-based page analysis.

- **Utils Layer** (`src/talk2browser/utils/`):  
  Provides utility functions for config, logging, selector filtering, and secret resolution.

---

## 2. Key Usage Patterns and Data Flow

- **LLM/Agent-Driven Workflow:**  
  The agent receives a user prompt, interprets it (often with an LLM), and determines which tools to invoke. Each tool (e.g., `click`, `fill`, `navigate`, `get_screenshot`) is a Python function, decorated and exposed for LLM use.

- **BrowserPage and DOMService:**  
  Each browser tab/page is represented by a `BrowserPage` object, which owns a `DOMService` instance.  
  - `DOMService` is responsible for scanning the DOM, maintaining element maps/histories, and providing element-level actions (click, type, highlight, etc.).
  - All element lookups and actions are routed through this service, ensuring a single source of truth for DOM state.

- **Action Recording:**  
  All actions (including tool calls, browser events, screenshots, etc.) are recorded via `ActionService`.  
  - This enables full replay, debugging, and audit trails.
  - Screenshot paths and other outputs are stored here for later use (e.g., PDF/report generation).

- **Tool Layer:**  
  The `browser_tools.py` file exposes most browser actions as LLM-callable tools, wrapping lower-level service and Playwright calls.  
  - Tools are stateless and operate on the current page/context as managed by the `PageManager`.
  - Some tools (like `get_screenshot`) support both immediate actions and history queries.

---

## 3. DOMService Design and Integration

- **Canonical DOMService:**  
  - Defined in `src/talk2browser/browser/dom/service.py`.
  - Instantiated per-page (not as a singleton), always tied to a Playwright `Page` object.
  - Provides methods for:
    - Scanning and mapping interactive elements (`get_interactive_elements`)
    - Element actions (`click_element`, `type_text`, etc.)
    - Element lookup by hash or description
    - Highlighting and clearing highlights
    - DOM tree retrieval and semantic search

- **Usage:**  
  - Accessed via `BrowserPage.get_dom_service()`.
  - All tool and agent logic should use the per-page instance, **never a global singleton**.
  - Any new DOM-related methods (e.g., calendar popup detection) should be added to this class and invoked via the current `BrowserPage`'s `dom_service`.

---

## 4. Typical End-to-End Flow

1. **User prompt** → Agent/LLM interprets → Issues tool calls (e.g., click, fill, screenshot).
2. **Tool call** (e.g., `click`) →  
   - Gets current `BrowserPage` from `PageManager`
   - Uses that page's `DOMService` to resolve/select/click the element
   - Records the action via `ActionService`
3. **DOM updates** (e.g., after click, calendar popup) →  
   - DOMService scans/refreshes interactive elements as needed
   - Optionally, LLM may call a tool to wait for a popup or refresh the DOM
4. **Reporting** (e.g., screenshots, PDF) →  
   - ActionService provides all recorded actions and outputs
   - LLM/toolchain can generate reports using these logs

---

## 5. Design Strengths

- **Separation of concerns:**  
  Agent, browser, DOM, tools, and services are cleanly separated.
- **Extensibility:**  
  New tools and DOM actions can be added without disrupting agent or browser logic.
- **Auditability:**  
  Full action recording and replay are built-in.
- **LLM/Tool-Driven:**  
  All high-level workflows are LLM-driven, with explicit tool calls for every action.

---

## 6. Best Practices for Extending

- **Add new DOM logic to the per-page `DOMService` in `browser/dom/service.py`.**
- **Expose new actions as tools in `browser_tools.py`, always referencing the current page's `DOMService`.**
- **Never create a global singleton for DOMService—always use the instance tied to the current BrowserPage.**
- **All action recording should go through ActionService.**

---

If you need a diagram or want a breakdown of a specific workflow or file, let me know!
