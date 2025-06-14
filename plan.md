# Project Plan: Playwright Script Generation and Sensitive Data Handling

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
