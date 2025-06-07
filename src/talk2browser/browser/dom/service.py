"""
DOM Service for interacting with the page DOM using buildDomTree.js.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

@dataclass
class DOMElement:
    """Represents a DOM element with its properties."""
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
        self.text = text
        self.bounds = bounds
        self.computed_style = computed_style or {}
        
    def __str__(self):
        return f"<DOMElement {self.tag_name} {self.xpath}>"
    
    def __repr__(self):
        return str(self)

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
        self.xpath_cache = {}
        self._script_content = self._load_script()
        
    def _load_script(self) -> str:
        """Load the buildDomTree.js script."""
        script_path = Path(__file__).parent / 'buildDomTree.js'
        return script_path.read_text(encoding='utf-8')
    
    async def get_dom_tree(self, highlight_elements: bool = False, focus_element: int = -1, viewport_expansion: int = 0) -> Dict:
        """Get the complete DOM tree with interactive elements highlighted.
        
        Args:
            highlight_elements: Whether to highlight interactive elements
            focus_element: Index of element to focus (-1 for none)
            viewport_expansion: Number of pixels to expand the viewport by
            
        Returns:
            Dictionary containing the DOM tree and element map
        """
        if await self.page.evaluate('1+1') != 2:
            raise ValueError('The page cannot evaluate javascript code properly')
            
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
            result = await self.page.evaluate(self._script_content, args)
            
            if 'error' in result:
                raise ValueError(f"Error getting DOM tree: {result['error']}")
                
            return result
            
        except Exception as e:
            logger.error('Error evaluating JavaScript: %s', e)
            raise
        
        return result
    
    async def get_interactive_elements(self, highlight: bool = False) -> List[DOMElement]:
        """Get all interactive elements on the page.
        
        Args:
            highlight: Whether to highlight the elements
            
        Returns:
            List of DOMElement objects
        """
        dom_tree = await self.get_dom_tree(highlight_elements=highlight)
        elements = []
        
        for elem_id, elem_data in dom_tree['map'].items():
            if elem_data.get('isInteractive'):
                try:
                    element = DOMElement(
                        tag_name=elem_data.get('tagName', '').lower(),
                        text=elem_data.get('text', ''),
                        xpath=elem_data.get('xpath', ''),
                        bounds=elem_data.get('bounds'),
                        is_interactive=True,
                        highlight_index=elem_data.get('highlightIndex'),
                        node_type=elem_data.get('nodeType', 1)  # Default to ELEMENT_NODE
                    )
                    elements.append(element)
                except Exception as e:
                    logger.warning(f"Error creating DOMElement: {e}")
                    continue
                    
        return elements
        """Recursively find all interactive elements."""
        if element.is_interactive:
            result.append(element)
        
        for child in element.children:
            self._find_interactive_elements(child, result)
    
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
