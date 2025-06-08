"""Tool registry for dynamic tool discovery and execution."""
import inspect
import logging
import asyncio
from typing import Any, Callable, Dict, List, Optional, Type, Tuple, Union
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from playwright.async_api import Page, ElementHandle
from ..browser.dom.service import DOMService

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing browser automation tools."""

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Dict] = {}
        self._register_base_tools()

    def _register_base_tools(self) -> None:
        """Dynamically register Playwright Page, ElementHandle, and DOM service methods as tools."""
        # Register Page methods
        page_methods = self._get_playwright_methods(Page)
        for name, method in page_methods.items():
            self._register_playwright_method(
                name=name,
                method=method,
                prefix="page_"
            )
        
        # Register ElementHandle methods
        element_methods = self._get_playwright_methods(ElementHandle)
        for name, method in element_methods.items():
            self._register_playwright_method(
                name=name,
                method=method,
                prefix="element_"
            )
            
        # Register DOM service methods
        self.register_tool(
            name="get_interactive_elements",
            func=self._get_interactive_elements,
            description="Get all interactive elements on the page with optional highlighting",
            parameters={
                "type": "object",
                "properties": {
                    "highlight": {
                        "type": "boolean",
                        "description": "Whether to highlight the interactive elements"
                    }
                }
            }
        )
        
        self.register_tool(
            name="clear_highlights",
            func=self._clear_highlights,
            description="Clear any existing element highlights from the page",
            parameters={"type": "object", "properties": {}}
        )
    
    def _get_playwright_methods(self, cls: Type) -> Dict[str, Callable]:
        """Get all public async methods from a Playwright class."""
        methods = {}
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith('_') and inspect.iscoroutinefunction(method):
                methods[name] = method
        return methods
    
    def _register_playwright_method(self, name: str, method: Callable, prefix: str = "") -> None:
        """Register a Playwright method as a tool."""
        # Skip methods that aren't safe to expose
        if name in ['wait_for_selector', 'wait_for_function']:  # Add more as needed
            return
            
        # Special handling for screenshot method
        if name == 'screenshot':
            self._register_screenshot_method(prefix)
            return
            
        # Get method signature and type hints
        sig = inspect.signature(method)
        params = {}
        required = []
        
        # Skip 'self' parameter
        parameters = list(sig.parameters.values())[1:]  # Skip 'self'
        
        # Convert parameters to JSON schema
        for param in parameters:
            param_info = {"type": "string"}  # Default type
            
            # Handle parameter type hints
            if param.annotation != inspect.Parameter.empty:
                # Handle string annotations (forward references)
                if isinstance(param.annotation, str):
                    type_str = param.annotation.lower()
                else:
                    # Handle actual type objects
                    type_str = (
                        param.annotation.__name__.lower()
                        if hasattr(param.annotation, '__name__')
                        else str(param.annotation).lower()
                    )
                
                # Map Python types to JSON schema types
                if 'int' in type_str:
                    param_info["type"] = "integer"
                elif 'bool' in type_str:
                    param_info["type"] = "boolean"
                elif 'dict' in type_str or 'Dict' in type_str:
                    param_info["type"] = "object"
                elif 'list' in type_str or 'List' in type_str:
                    param_info["type"] = "array"
                elif 'str' in type_str or 'string' in type_str:
                    param_info["type"] = "string"
                elif 'float' in type_str:
                    param_info["type"] = "number"
                elif 'locator' in type_str.lower():
                    # Handle Playwright Locator objects
                    param_info["type"] = "object"
                    param_info["description"] = "A Playwright Locator object"
            
            # Skip internal parameters (prefixed with _)
            if param.name.startswith('_'):
                continue
                
            # Add parameter description if available
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            else:
                required.append(param.name)
            
            params[param.name] = param_info
        
        # Create the tool schema
        schema = {
            "type": "object",
            "properties": params,
            "required": required
        }
        
        # Create a wrapper function that will be called with the browser context
        async def method_wrapper(**kwargs):
            # This will be replaced when the tool is executed
            page = kwargs.pop('_page', None)
            element = kwargs.pop('_element', None)
            
            if page and hasattr(page, name):
                return await getattr(page, name)(**kwargs)
            elif element and hasattr(element, name):
                return await getattr(element, name)(**kwargs)
            else:
                raise ValueError(f"Method {name} not found on page or element")
        
        # Register the tool
        tool_name = f"{prefix}{name}"
        self._tools[tool_name] = {
            "name": tool_name,
            "function": method_wrapper,
            "description": f"Playwright {tool_name} method",
            "parameters": schema
        }
        
    def _register_screenshot_method(self, prefix: str = "") -> None:
        """Register a custom screenshot method with proper parameter handling."""
        from typing import Optional, Union, Dict, Any
        from pathlib import Path
        
        async def screenshot(
            _page=None,
            path: Optional[Union[str, Path]] = None,
            type: Optional[str] = None,
            quality: Optional[int] = None,
            full_page: bool = False,
            clip: Optional[Dict[str, float]] = None,
            animations: str = "disabled",
            caret: str = "hide",
            scale: str = "css",
            mask_color: str = "#00000080",
            omit_background: bool = False,
            timeout: Optional[float] = None,
            **kwargs: Any
        ) -> bytes:
            """Take a screenshot of the current page or a specific element.
            
            Args:
                _page: The Playwright page object (automatically injected)
                path: File path to save the image to. If not provided, the image will be returned as bytes.
                type: Specify screenshot type, can be either 'jpeg' or 'png'.
                quality: The quality of the image, between 0-100. Not applicable to png images.
                full_page: When True, takes a screenshot of the full scrollable page.
                clip: An object which specifies clipping region of the page.
                animations: When set to 'disabled', stops CSS animations and transitions.
                caret: When set to 'hide', screenshot will hide text caret.
                scale: When set to 'css', scales the page to match the CSS layout.
                mask_color: The color to use for masking elements.
                omit_background: Hides default white background and allows capturing screenshots with transparency.
                timeout: Maximum time in milliseconds. Defaults to 30 seconds.
                
            Returns:
                bytes: The screenshot image data.
            """
            if not _page:
                raise ValueError("Page object is required for taking screenshots")
                
            screenshot_args = {
                'path': path,
                'type': type,
                'quality': quality,
                'full_page': full_page,
                'clip': clip,
                'animations': animations,
                'caret': caret,
                'scale': scale,
                'mask_color': mask_color,
                'omit_background': omit_background,
                'timeout': timeout
            }
            
            # Remove None values
            screenshot_args = {k: v for k, v in screenshot_args.items() if v is not None}
            
            return await _page.screenshot(**screenshot_args)
        
        # Register the screenshot tool with proper schema
        tool_name = f"{prefix}screenshot"
        self._tools[tool_name] = {
            "name": tool_name,
            "function": screenshot,
            "description": "Take a screenshot of the current page or a specific element",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to save the screenshot to. If not provided, returns the image as base64."
                    },
                    "type": {
                        "type": "string",
                        "enum": ["png", "jpeg"],
                        "description": "Image compression format. Defaults to 'png'."
                    },
                    "quality": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "The quality of the image, between 0-100. Not applicable to png images."
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "When true, takes a screenshot of the full scrollable page. Defaults to false.",
                        "default": False
                    },
                    "clip": {
                        "type": "object",
                        "description": "An object which specifies clipping region of the page.",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "width": {"type": "number"},
                            "height": {"type": "number"}
                        },
                        "required": ["x", "y", "width", "height"]
                    },
                    "animations": {
                        "type": "string",
                        "enum": ["allow", "disabled"],
                        "description": "When set to 'disabled', stops CSS animations and transitions. Defaults to 'disabled'.",
                        "default": "disabled"
                    },
                    "caret": {
                        "type": "string",
                        "enum": ["hide", "initial"],
                        "description": "When set to 'hide', screenshot will hide text caret. Defaults to 'hide'.",
                }
            }
        }
    }
        
    def register_tool(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: Dict[str, Any],
    ) -> None:
        """Register a new tool.

        Args:
            name: Name of the tool
            func: Callable that implements the tool
            description: Description of what the tool does
            parameters: JSON schema for the tool's parameters
        """
        self._tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameters,
        }

    def get_tool(self, name: str) -> Optional[Dict]:
        """Get a tool by name.

        Args:
            name: Name of the tool to get

        Returns:
            Tool definition or None if not found
        """
        return self._tools.get(name)

    def _get_tool_texts(self, tools: List[Dict]) -> List[str]:
        """Get text representations of tools for vectorization."""
        return [f"{t['name']} {t['description']}" for t in tools]

    def match_tools(self, user_input: str, tools: List[Dict], top_k: int = 5) -> List[Dict]:
        """Match tools to user input using TF-IDF and cosine similarity.
        
        Args:
            user_input: The user's input text
            tools: List of tool dictionaries to match against
            top_k: Number of top matches to return
            
        Returns:
            List of top matching tools with scores
        """
        if not tools or not user_input.strip():
            return []
            
        tool_texts = self._get_tool_texts(tools)
        
        # Initialize and fit the vectorizer
        vectorizer = TfidfVectorizer()
        try:
            tool_vectors = vectorizer.fit_transform(tool_texts)
            user_vector = vectorizer.transform([user_input])
            
            # Calculate similarity scores
            scores = cosine_similarity(user_vector, tool_vectors)[0]
            
            # Get top k matches
            matched = sorted(zip(tools, scores), key=lambda x: -x[1])[:top_k]
            return [{"tool": tool, "score": float(score)} for tool, score in matched]
            
        except Exception as e:
            logger.warning(f"Error matching tools: {e}")
            return [{"tool": t, "score": 0.0} for t in tools[:top_k]]  # Fallback to first N tools

    def list_tools(
        self, 
        user_input: Optional[str] = None, 
        page_state: Optional[Dict] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """List available tools, filtered by relevance to user input and page state.
        
        Args:
            user_input: Optional input text to filter tools by relevance
            page_state: Optional current page state with URL and interactive elements
            top_k: Maximum number of tools to return
            
        Returns:
            List of tool definitions sorted by relevance
        """
        all_tools = [
            {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
            for name, tool in self._tools.items()
        ]
        
        # Build context-aware query
        query_parts = []
        if user_input:
            query_parts.append(user_input)
            
        if page_state:
            # Add URL context
            if url := page_state.get('url'):
                query_parts.append(f"url: {url}")
                
            # Add interactive elements context (limit to 5)
            if elements := page_state.get('interactive_elements', [])[:5]:
                element_descs = []
                for elem in elements:
                    elem_type = elem.get('type', 'element')
                    elem_desc = elem.get('description', '')
                    if elem_desc:
                        element_descs.append(f"{elem_type}: {elem_desc}")
                if element_descs:
                    query_parts.append("elements: " + ", ".join(element_descs))
        
        # Create combined query
        query = " ".join(query_parts)
        
        if query:
            matched = self.match_tools(query, all_tools, top_k=top_k)
            return [m["tool"] for m in matched]
            
        return all_tools[:top_k]

    async def _get_interactive_elements(self, _page=None, highlight: bool = False) -> List[Dict]:
        """Get all interactive elements on the page with optional highlighting.
        
        Args:
            _page: Playwright page object
            highlight: Whether to highlight the elements
            
        Returns:
            List of interactive elements
        """
        dom_service = DOMService(_page)
        elements = await dom_service.get_interactive_elements(highlight=highlight)
        return [e.to_dict() for e in elements]
    
    async def _clear_highlights(self, _page=None) -> None:
        """Clear any existing element highlights from the page.
        
        Args:
            _page: Playwright page object
        """
        dom_service = DOMService(_page)
        await dom_service.clear_highlights()
    
    async def execute_tool(self, name: str, _page=None, **kwargs) -> Any:
        """Execute a tool by name with the given arguments.
        
        Args:
            name: Name of the tool to execute
            _page: Playwright page object (injected by agent)
            **kwargs: Arguments to pass to the tool
            
        Returns:
            The result of the tool execution
            
        Raises:
            ValueError: If the tool is not found or page is not provided
        """
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")
            
        if _page is None:
            raise ValueError("Page object is required for tool execution")
            
        tool = self._tools[name]
        
        try:
            # Add page to tool arguments with correct name
            kwargs["_page"] = _page
            
            # Handle locator parameters
            if "locator" in str(inspect.signature(tool["function"])).lower():
                # Convert string locator to Playwright Locator object
                if isinstance(kwargs.get("locator"), str):
                    kwargs["locator"] = _page.locator(kwargs["locator"])
            
            # Special handling for DOM service tools
            if name in ["get_interactive_elements", "clear_highlights"]:
                from ..browser.dom.service import DOMService
                dom_service = DOMService(_page)
                if name == "get_interactive_elements":
                    return await dom_service.get_interactive_elements(**kwargs)
                elif name == "clear_highlights":
                    return await dom_service.clear_highlights()
            
            # Execute the tool and await if it's a coroutine
            result = tool["function"](**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
                
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            raise
