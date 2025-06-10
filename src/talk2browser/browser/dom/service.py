"""
DOM Service for interacting with the page DOM using buildDomTree.js.
"""
from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from playwright.async_api import Page

logger = logging.getLogger(__name__)

@dataclass
class DOMElement:
    """Represents a DOM element with its properties and provides hashing for identification."""
    
    def __init__(
        self,
        tag_name: str,
        xpath: str,
        attributes: Dict[str, str] = None,
        is_visible: bool = False,
        is_interactive: bool = False,
        is_top_element: bool = False,
        is_in_viewport: bool = False,
        highlight_index: Optional[int] = None,
        text: Optional[str] = None,
        bounds: Optional[Dict[str, int]] = None,
        computed_style: Optional[Dict[str, str]] = None,
        node_type: int = 1,  # Default to ELEMENT_NODE
    ):
        self.node_type = node_type
        self.tag_name = tag_name
        self.xpath = xpath
        self.attributes = attributes or {}
        self.is_visible = is_visible
        self.is_interactive = is_interactive
        self.is_top_element = is_top_element
        self.is_in_viewport = is_in_viewport
        self.highlight_index = highlight_index
        self.text = (text or '').strip()
        self.bounds = bounds or {}
        self.computed_style = computed_style or {}
        self._element_hash: Optional[str] = None
        
    def __str__(self):
        return f"<DOMElement {self.tag_name} {self.xpath}>"
    
    def __repr__(self):
        return str(self)
        
    @property
    def element_hash(self) -> str:
        """Generate a stable hash for the element based on its properties."""
        if self._element_hash is None:
            # Create a unique identifier based on element's properties
            hash_data = {
                'tag': self.tag_name,
                'xpath': self.xpath,
                'text': self.text,
                'classes': self.attributes.get('class', '').split(),
                'type': self.attributes.get('type'),
                'id': self.attributes.get('id'),
                'name': self.attributes.get('name'),
                'role': self.attributes.get('role'),
                'aria-label': self.attributes.get('aria-label'),
                'placeholder': self.attributes.get('placeholder'),
            }
            # Convert to JSON string and hash it
            hash_str = json.dumps(hash_data, sort_keys=True)
            self._element_hash = hashlib.md5(hash_str.encode('utf-8')).hexdigest()
        return self._element_hash
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert element to a dictionary for serialization."""
        return {
            'hash': self.element_hash,
            'tag_name': self.tag_name,
            'xpath': self.xpath,
            'text': self.text,
            'is_visible': self.is_visible,
            'is_interactive': self.is_interactive,
            'attributes': self.attributes,
            'bounds': self.bounds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DOMElement':
        """Create a DOMElement from a dictionary."""
        children = [cls.from_dict(child) for child in data.get('children', [])]
        return cls(
            tag_name=data.get('tagName', '').lower(),
            xpath=data.get('xpath', ''),
            attributes=data.get('attributes', {}),
            is_visible=data.get('isVisible', False),
            is_interactive=data.get('isInteractive', False),
            is_top_element=data.get('isTopElement', False),
            is_in_viewport=data.get('isInViewport', False),
            highlight_index=data.get('highlightIndex'),
            text=data.get('text', ''),
            children=children,
            bounds=data.get('bounds'),
            computed_style=data.get('computedStyle', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the DOMElement to a dictionary."""
        return {
            'nodeType': self.node_type,
            'tagName': self.tag_name,
            'xpath': self.xpath,
            'attributes': self.attributes,
            'isVisible': self.is_visible,
            'isInteractive': self.is_interactive,
            'isTopElement': self.is_top_element,
            'isInViewport': self.is_in_viewport,
            'highlightIndex': self.highlight_index,
            'text': self.text,
            'children': [child.to_dict() for child in self.children],
            'bounds': self.bounds,
            'computedStyle': self.computed_style
        }

class DOMService:
    """Service for interacting with the page DOM using buildDomTree.js."""
    
    def __init__(self, page: Page):
        self.page = page
        self._dom_tree = None
        self._interactive_elements: List[DOMElement] = []
        self._highlighted_elements = set()
        self._element_map: Dict[str, DOMElement] = {}
        
        # Load the buildDomTree.js script
        script_path = Path(__file__).parent / "buildDomTree.js"
        with open(script_path, "r", encoding='utf-8') as f:
            self._build_dom_tree_js = f.read()
            
    async def get_interactive_elements(self, highlight: bool = False) -> List[Dict[str, Any]]:
        """Get all interactive elements on the page with their hashes.
        
        Args:
            highlight: Whether to highlight the elements
            
        Returns:
            List of element dictionaries with hashes
        """
        elements = []
        dom_tree = await self._get_dom_tree(highlight_elements=highlight)
        
        for elem_id, elem_data in dom_tree['map'].items():
            if elem_data.get('isInteractive'):
                element = DOMElement(
                    tag_name=elem_data.get('tagName', '').lower(),
                    text=elem_data.get('text', '').strip(),
                    xpath=elem_data.get('xpath', ''),
                    attributes=elem_data.get('attributes', {}),
                    is_visible=elem_data.get('isVisible', False),
                    is_interactive=True,
                    is_in_viewport=elem_data.get('isInViewport', False),
                    bounds=elem_data.get('bounds'),
                    highlight_index=elem_data.get('highlightIndex'),
                )
                self._element_map[element.element_hash] = element
                elements.append(element.to_dict())
                
        self._interactive_elements = elements
        return elements
        
    async def find_element_by_hash(self, element_hash: str) -> Optional[DOMElement]:
        """Find an interactive element by its hash.
        
        Args:
            element_hash: The hash of the element to find
            
        Returns:
            The matching DOMElement or None if not found
        """
        if not self._interactive_elements:
            await self.get_interactive_elements()
            
        return self._element_map.get(element_hash)
        
    async def get_interactive_elements(self, highlight: bool = False) -> List[DOMElement]:
        """Get all interactive elements on the page with their hashes.
        
        Args:
            highlight: Whether to highlight the elements
            
        Returns:
            List of interactive DOMElement objects
        """
        logger.info('Scanning page for interactive elements...')
        
        # Clear previous element map
        self._element_map = {}
        elements = []
        
        try:
            # Get all potentially interactive elements
            selector = ', '.join([
                'input[type=text]',
                'input[type=password]',
                'input[type=email]',
                'input[type=number]',
                'input[type=search]',
                'input[type=tel]',
                'input[type=url]',
                'input[type=submit]',
                'input[type=button]',
                'input[type=reset]',
                'textarea',
                'select',
                'button',
                'a[href]',
                '[role=button]',
                '[role=link]',
                '[role=tab]',
                '[role=menuitem]',
                '[role=option]',
                '[role=checkbox]',
                '[role=radio]',
                '[role=switch]',
                '[role=textbox]',
                '[role=searchbox]',
                '[role=combobox]',
                '[role=spinbutton]',
                '[onclick]',
                '[onmousedown]',
                '[onmouseup]',
                '[onkeydown]',
                '[onkeyup]'
            ])
            
            # Get fresh DOM tree
            dom_tree = await self.get_dom_tree(highlight_elements=highlight)
            
            # Process interactive elements
            for elem_id, elem_data in dom_tree['map'].items():
                if elem_data.get('isInteractive'):
                    element = DOMElement(
                        tag_name=elem_data.get('tagName', '').lower(),
                        text=elem_data.get('text', '').strip(),
                        xpath=elem_data.get('xpath', ''),
                        attributes=elem_data.get('attributes', {}),
                        is_visible=elem_data.get('isVisible', False),
                        is_interactive=True,
                        is_in_viewport=elem_data.get('isInViewport', False),
                        bounds=elem_data.get('bounds'),
                        highlight_index=elem_data.get('highlightIndex'),
                    )
                    logger.debug(f"Adding element to map: {element.tag_name} - {element.element_hash}")
                    self._element_map[element.element_hash] = element
                    elements.append(element)
                    
            logger.debug(f"Found {len(elements)} elements, map size: {len(self._element_map)}")
            return elements
            
        except Exception as e:
            logger.error(f"Error getting interactive elements: {e}")
            return []
            
        logger.debug(f"Found {len(elements)} elements, map size: {len(self._element_map)}")
        return elements
        
    async def click_element_by_hash(self, element_hash: str) -> bool:
        """Click an element by its hash.
        
        Args:
            element_hash: The hash of the element to click
            
        Returns:
            bool: True if click was successful, False otherwise
        """
        # Get element from current map without refreshing
        logger.debug(f"Looking for element with hash {element_hash} in map of size {len(self._element_map)}")
        element = self._element_map.get(element_hash)
        if not element:
            logger.warning("Element with hash %s not found in current map", element_hash)
            return False
            
        try:
            # Use locator for better dynamic element handling
            logger.debug(f"Found element {element.tag_name}, using xpath: {element.xpath}")
            locator = self.page.locator(f'xpath={element.xpath}')
            await locator.wait_for(state='visible', timeout=5000)
            await locator.click()
            return True
        except Exception as e:
            logger.error(f"Error clicking element: {e}")
            return False
            
    async def get_dom_tree(self, highlight_elements: bool = False, focus_element: int = -1, viewport_expansion: int = 0) -> Dict:
        """Get the complete DOM tree with interactive elements highlighted.
        
        Args:
            highlight_elements: Whether to highlight interactive elements
            focus_element: Index of the element to highlight (-1 for none)
            viewport_expansion: Number of pixels to expand the viewport by when checking visibility
            
        Returns:
            Dictionary containing the DOM tree and element map
        """
        try:
            if await self.page.evaluate('1+1') != 2:
                logger.error('JavaScript evaluation test failed')
                raise ValueError('The page cannot evaluate javascript code properly')
        except Exception as e:
            logger.error(f'JavaScript evaluation error: {e}')
            raise ValueError('JavaScript evaluation failed') from e
            
        if self.page.url == 'about:blank':
            # Return empty tree for blank page
            return {
                'rootId': 'root',
                'map': {
                    'root': {
                        'tag_name': 'body',
                        'xpath': '',
                        'attributes': {},
                        'children': [],
                        'isVisible': False
                    }
                }
            }
            
        # Pass arguments to buildDomTree
        args = {
            'doHighlightElements': highlight_elements,
            'focusHighlightIndex': focus_element,
            'viewportExpansion': viewport_expansion,
            'debugMode': False
        }
        
        try:
            result = await self.page.evaluate(self._build_dom_tree_js, args)
            
            if 'error' in result:
                raise ValueError(f"Error getting DOM tree: {result['error']}")
                
            return result
            
        except Exception as e:
            logger.error('Error evaluating JavaScript: %s', e)
            raise
        
        return result
    

    
    async def _highlight_elements(self, elements: List[DOMElement]):
        """Highlight the given elements on the page."""
        if not elements:
            return
            
        # Create a simple highlight overlay
        highlight_script = """
        function highlightElements(elements) {
            // Remove existing highlights
            const container = document.getElementById('talk2browser-highlights');
            if (container) {
                container.remove();
            }
            
            // Create container
            const newContainer = document.createElement('div');
            newContainer.id = 'talk2browser-highlights';
            newContainer.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 0;
                height: 0;
                z-index: 2147483647;
                pointer-events: none;
            `;
            document.body.appendChild(newContainer);
            
            // Color map for different element types
            const colors = {
                'a': '#4ECDC4',      // Teal for links
                'button': '#FF6B6B',  // Red for buttons
                'input': '#45B7D1',   // Blue for inputs
                'select': '#96CEB4',  // Green for selects
                'default': '#D4A373'  // Tan for others
            };
            
            // Add highlights
            elements.forEach((elem, index) => {
                try {
                    const element = document.evaluate(
                        elem.xpath,
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                    
                    if (element) {
                        const rect = element.getBoundingClientRect();
                        const highlight = document.createElement('div');
                        const color = colors[elem.tag_name] || colors.default;
                        
                        highlight.className = 'talk2browser-highlight';
                        highlight.style.cssText = `
                            position: absolute;
                            left: ${rect.left + window.scrollX}px;
                            top: ${rect.top + window.scrollY}px;
                            width: ${rect.width}px;
                            height: ${rect.height}px;
                            background-color: ${color}33;
                            border: 2px solid ${color};
                            pointer-events: none;
                            box-sizing: border-box;
                        `;
                        
                        // Add label
                        const label = document.createElement('div');
                        label.textContent = index + 1;
                        label.style.cssText = `
                            position: absolute;
                            top: -20px;
                            left: 0;
                            background-color: ${color};
                            color: white;
                            font-size: 12px;
                            padding: 2px 5px;
                            border-radius: 3px;
                            font-family: Arial, sans-serif;
                        `;
                        
                        highlight.appendChild(label);
                        newContainer.appendChild(highlight);
                    }
                } catch (e) {
                    console.error('Error highlighting element:', e);
                }
            });
        }
        """
        
        # Call the highlight function
        elements_data = [{
            'xpath': elem.xpath,
            'tag_name': elem.tag_name,
            'highlight_index': i
        } for i, elem in enumerate(elements)]
        
        await self.page.evaluate(f"""
            {highlight_script}
            highlightElements({json.dumps(elements_data)});
        """)
    
    async def clear_highlights(self):
        """Clear any existing element highlights."""
        await self.page.evaluate("""
            const highlights = document.querySelectorAll('.talk2browser-highlight');
            highlights.forEach(h => h.remove());
        """)
        
    async def find_best_match(self, description: str) -> Optional[DOMElement]:
        """Find the best matching element for the given description.
        
        Args:
            description: Natural language description of the element
            
        Returns:
            Best matching DOMElement or None if no match found
        """
        elements = await self.get_interactive_elements(highlight=True)
        
        if not elements:
            return None
            
        # Simple text matching for now
        # TODO: Use embeddings for better semantic matching
        description = description.lower()
        best_match = None
        best_score = 0
        
        for element in elements:
            score = 0
            
            # Check text content
            if element.text:
                text = element.text.lower()
                if description in text:
                    score += 2
                elif text in description:
                    score += 1
                    
            # Check tag name
            if element.tag_name in description:
                score += 1
                
            if score > best_score:
                best_score = score
                best_match = element
                
        return best_match
        
    async def click_element(self, element: DOMElement):
        """Click on the specified element.
        
        Args:
            element: Element to click
        """
        if not element.xpath:
            raise ValueError("Element has no XPath")
            
        try:
            await self.page.locator(f"xpath={element.xpath}").click()
            return True
        except Exception as e:
            logger.error(f"Error clicking element: {e}")
            return False
    
    async def type_text(self, element: DOMElement, text: str):
        """Type text into the specified element.
        
        Args:
            element: The DOM element to type into
            text: The text to type
        """
        try:
            await self.page.fill(f'xpath={element.xpath}', text)
            return True
        except Exception as e:
            logger.error(f"Error typing text: {e}")
            return False