"""DOM Service for interacting with the page DOM using buildDomTree.js."""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
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
    # ... existing methods ...

    async def show_manual_mode_timeout_popup(self):
        """
        Injects a popup into the browser to prompt the user to resume agent mode after a manual mode timeout.
        """
        logger.info("Injecting manual mode timeout popup into the browser.")
        await self.page.evaluate("""
            if (!document.getElementById('manualTimeoutPopup')) {
              const popup = document.createElement('div');
              popup.id = 'manualTimeoutPopup';
              popup.innerHTML = '<div style="padding: 24px; background: rgba(34,40,49,0.95); color: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(31,38,135,0.37); text-align: center; font-size: 1.1em;">Manual mode has been active for a while.<br><br><button id="resumeAgentBtn" style="margin: 8px; padding: 8px 16px; background: #2196f3; color: white; border: none; border-radius: 6px;">Resume Agent</button><button id="continueManualBtn" style="margin: 8px; padding: 8px 16px; background: #757575; color: white; border: none; border-radius: 6px;">Continue Manual</button></div>';
              document.body.appendChild(popup);
              document.getElementById('resumeAgentBtn').onclick = () => {
                window.setAgentMode && window.setAgentMode();
                popup.remove();
              };
              document.getElementById('continueManualBtn').onclick = () => {
                popup.remove();
              };
            }
        """)


    """Service for interacting with the page DOM using buildDomTree.js."""
    
    def __init__(self, page: Page):
        """Initialize the DOM service with a persistent element history map."""
        self.page = page
        self._element_history_map: Dict[str, DOMElement] = {}
        self._last_page_url: Optional[str] = None
        self._build_dom_tree_js = None
        # Load buildDomTree.js script
        script_path = os.path.join(os.path.dirname(__file__), 'buildDomTree.js')
        try:
            with open(script_path, 'r') as f:
                self._build_dom_tree_js = f.read()
                logger.debug('Successfully loaded buildDomTree.js')
        except Exception as e:
            logger.error('Failed to load buildDomTree.js: %s', e)
            raise ValueError(f'Could not load buildDomTree.js from {script_path}') from e
            
    async def get_interactive_elements(self, highlight: bool = False) -> List[DOMElement]:
        """Get all interactive elements on the page using a persistent history map."""
        logger.info('Scanning page for interactive elements...')
        try:
            current_url = self.page.url if isinstance(self.page.url, str) else await self.page.url
            if self._last_page_url != current_url:
                self._element_history_map.clear()
                logger.debug(f"Page reload detected (old: {self._last_page_url}, new: {current_url}), cleared element history map.")
            self._last_page_url = current_url

            dom_tree = await self.get_dom_tree(highlight_elements=highlight)
            if not dom_tree or 'map' not in dom_tree:
                logger.error('Invalid DOM tree response')
                return []

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
                    # --- Minimal enhancement: enrich attributes dict ---
                    attributes = element.attributes
                    # Ensure role
                    if 'role' not in attributes:
                        role = elem_data.get('attributes', {}).get('role')
                        if role:
                            attributes['role'] = role
                    # Ensure placeholder
                    if 'placeholder' not in attributes:
                        placeholder = elem_data.get('attributes', {}).get('placeholder')
                        if placeholder:
                            attributes['placeholder'] = placeholder
                    # Add all aria-* attributes
                    for k, v in elem_data.get('attributes', {}).items():
                        if k.startswith('aria-'):
                            attributes[k] = v
                    # Try to get associated label text from attributes if present
                    label = elem_data.get('attributes', {}).get('label')
                    if label:
                        attributes['label'] = label.strip()
                    element.attributes = attributes
                    # --- End enhancement ---
                    h = element.element_hash
                    if h in self._element_history_map:
                        self._element_history_map[h].__dict__.update(element.__dict__)
                        logger.debug(f"Element updated in history: {h}")
                    else:
                        self._element_history_map[h] = element
                        logger.debug(f"Element added to history: {h}")
                    # Debug: Output full attributes and text for this element
                    logger.debug(f"[ElementMap] Hash: {h} | tag: {element.tag_name} | text: '{element.text}' | attributes: {json.dumps(element.attributes)}")
            logger.info(f"History map size after scan: {len(self._element_history_map)}")
            return list(self._element_history_map.values())
        except Exception as e:
            logger.error(f"Error getting interactive elements: {e}", exc_info=True)
            return []
        
    async def find_element_by_hash(self, element_hash: str) -> Optional[DOMElement]:
        """Find an interactive element by its hash using the persistent history map."""
        h = element_hash.lstrip('#')
        if not self._element_history_map:
            await self.get_interactive_elements()
        element = self._element_history_map.get(h)
        if element:
            logger.debug(f"Found element by hash: {h}")
        else:
            logger.warning(f"Element with hash {h} not found in history map.")
        return element

    async def get_interactive_elements(self, highlight: bool = False) -> List[DOMElement]:
        """Get all interactive elements on the page with their hashes using buildDomTree.js.
        
        Args:
            highlight: Whether to highlight the elements
            
        Returns:
            List of interactive DOMElement objects
        """
        logger.info('Scanning page for interactive elements...')
        try:
            # Reset state
            self._interactive_elements = []
            self._element_map = {}
            
            # Get DOM tree using buildDomTree.js
            dom_tree = await self.get_dom_tree(highlight_elements=highlight)
            
            if not dom_tree or 'map' not in dom_tree:
                logger.error('Invalid DOM tree response')
                return []
                
            # Process interactive elements from DOM tree
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
                    
                    # Add element with # prefix hash
                    element_hash = f"#{element.element_hash}"
                    logger.debug(f"Found interactive {element.tag_name}: {element_hash}")
                    
                    # Store xpath in element map
                    self._element_map[element_hash] = element.xpath
                    self._interactive_elements.append(element)
            
            num_elements = len(self._interactive_elements)
            logger.info(f"Found {num_elements} interactive elements")
            
            if highlight and num_elements > 0:
                await self._highlight_elements(self._interactive_elements)
            
            return self._interactive_elements
            
        except Exception as e:
            logger.error(f"Error scanning for interactive elements: {e}", exc_info=True)
            return []
        
    async def click_element_by_hash(self, element_hash: str) -> bool:
        """Click an element by its hash using the persistent history map."""
        h = element_hash.lstrip('#')
        logger.debug(f"Looking for element with hash {h}")
        element = self._element_history_map.get(h)
        if not element:
            logger.warning(f"Element with hash {h} not found in history map (size: {len(self._element_history_map)})")
            await self.get_interactive_elements()
            element = self._element_history_map.get(h)
            if not element:
                logger.error(f"Element {h} not found even after refresh")
                return False
        try:
            xpath = element.xpath
            logger.debug(f"Found element, using xpath: {xpath}")
            locator = self.page.locator(f'xpath={xpath}')
            await locator.wait_for(state='visible', timeout=5000)
            await locator.scroll_into_view_if_needed()
            await locator.click()
            logger.info(f"Successfully clicked element {h}")
            return True
        except Exception as e:
            logger.error(f"Error clicking element {h}: {e}", exc_info=True)
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
        logger.debug('Getting DOM tree with highlight=%s, focus=%d', highlight_elements, focus_element)
        
        # First verify JavaScript evaluation works
        try:
            if await self.page.evaluate('1+1') != 2:
                raise ValueError('The page cannot evaluate javascript code properly')
        except Exception as e:
            logger.error('JavaScript evaluation failed: %s', e)
            raise ValueError('JavaScript evaluation failed - page may be in invalid state') from e
            
        if self.page.url == 'about:blank':
            logger.debug('Blank page detected, returning empty tree')
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
            
            if not result or not isinstance(result, dict):
                raise ValueError(f'Invalid DOM tree result: {result}')
                
            if 'error' in result:
                raise ValueError(f'Error in buildDomTree.js: {result["error"]}')
                
            logger.debug('Successfully retrieved DOM tree with %d nodes', 
                        len(result.get('map', {})))
            return result
            
        except Exception as e:
            logger.error('Error evaluating buildDomTree.js: %s', e)
            raise ValueError('Failed to build DOM tree') from e
            raise
        
        return result
    

    
    async def _highlight_elements(self, elements: List[DOMElement]):
        """Highlight the given elements on the page using the global JS function from buildDomTree.js."""
        import logging
        logger = logging.getLogger(__name__)
        if not elements:
            logger.debug("No elements to highlight.")
            return

        # Prepare data for JS: you may need to adjust structure to match expected input
        elements_data = [
            {
                'xpath': elem.xpath,
                'tag_name': elem.tag_name,
                'highlight_index': i
            }
            for i, elem in enumerate(elements)
        ]

        logger.debug(f"Calling window.highlightElements with {len(elements_data)} elements.")
        try:
            await self.page.evaluate(
                "(args) => window.highlightElements(args.elements, args.focusIndex)",
                {"elements": elements_data, "focusIndex": None}
            )
            logger.debug("Successfully called window.highlightElements.")
        except Exception as e:
            logger.error(f"Error calling window.highlightElements: {e}", exc_info=True)

    
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
            
    def format_elements(self) -> Tuple[str, Dict[str, str]]:
        """Format interactive elements into a human-readable string and return element map.
        
        Returns:
            Tuple of (formatted_elements_string, element_map)
        """
        element_descriptions = []
        for idx, element in enumerate(self._interactive_elements):
            if element.is_interactive and element.is_visible:
                element_hash = f"#{element.element_hash}"
                desc_parts = [f"{idx + 1}. {element_hash} - {element.tag_name}"]
                if element.attributes.get('id'):
                    desc_parts.append(f"id={element.attributes['id']}")
                if element.text:
                    text = element.text[:30] + ('...' if len(element.text) > 30 else '')
                    desc_parts.append(f"text='{text}'")
                element_descriptions.append(' '.join(desc_parts))
        
        elements_context = "\n".join([
            "Interactive elements on page (use #hash to reference):",
            *element_descriptions,
            f"\nTotal interactive elements: {len(element_descriptions)}"
        ])
        
        logger.debug(f"Formatted {len(element_descriptions)} elements")
        return elements_context, self.get_element_map()

    def get_element_map(self) -> Dict[str, str]:
        """Get the current element map (for debugging only; avoid external use)."""
        if not self._element_map:
            logger.warning("Element map is empty")
        return self._element_map.copy()  # Return a copy to prevent external modification

    def resolve_selector_hash(self, hash_val: str) -> str | None:
        """
        Resolve a hash value to a selector using the internal element map.
        Args:
            hash_val: The hash string (with or without # prefix)
        Returns:
            The resolved selector string, or None if not found
        """
        # Accept both '#abc123' and 'abc123'
        clean_hash = hash_val[1:] if hash_val.startswith('#') else hash_val
        for key, selector in self._element_map.items():
            if key.lstrip('#') == clean_hash:
                logger.debug(f"Resolved selector hash {hash_val} to: {selector}")
                return selector
        logger.error(f"Could not resolve selector hash: {hash_val}")
        return None