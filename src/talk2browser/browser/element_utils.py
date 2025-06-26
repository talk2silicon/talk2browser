"""Element discovery and interaction utilities."""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from playwright.async_api import ElementHandle, Page


@dataclass
class InteractiveElement:
    """Represents an interactive element on the page."""
    tag: str
    text: str
    type: str = ""
    id: str = ""
    name: str = ""
    placeholder: str = ""
    value: str = ""
    selector: str = ""
    attributes: Dict[str, str] = None
    is_visible: bool = True
    is_enabled: bool = True
    bounds: Dict[str, int] = None


async def find_interactive_elements(page: Page, max_elements: int = 100) -> List[Dict[str, Any]]:
    """Find all interactive elements on the page.
    
    Args:
        page: Playwright page object
        max_elements: Maximum number of elements to return
        
    Returns:
        List of interactive element dictionaries
    """
    # Common interactive element selectors
    selectors = [
        'a[href]',
        'button',
        'input:not([type=hidden])',
        'select',
        'textarea',
        '[role="button"]',
        '[role="link"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="textbox"]',
        '[tabindex]:not([tabindex="-1"])',
        '[onclick]',
        '[onmousedown]',
        '[onmouseup]',
        '[data-action]',
        '[data-link]',
        '[data-click]',
        '[style*="cursor:pointer"]',
        '.clickable',
        '.card',
        '.product',
        '.tile',
        '.item',
        '.btn',
        '.link'
    ]

    import logging
    logger = logging.getLogger(__name__)

    
    # Find all matching elements
    elements = []
    for selector in selectors:
        if len(elements) >= max_elements:
            break
            
        try:
            handles = await page.query_selector_all(selector)
            for handle in handles:
                if len(elements) >= max_elements:
                    break
                    
                # Skip if element is not visible
                if not await handle.is_visible():
                    continue

                # Get element properties
                element = await _get_element_properties(handle, selector)
                if element:
                    logger.debug(f"[find_interactive_elements] Detected element: tag={element['tag']}, text='{element['text']}', selector='{selector}', attributes={element.get('attributes',{})}")
                    elements.append(element)
        except Exception as e:
            # Skip if selector fails
            continue
    
    return elements


async def _get_element_properties(handle: ElementHandle, selector: str) -> Optional[Dict[str, Any]]:
    """Extract properties from an element handle."""
    try:
        # Get basic properties
        tag_name = (await handle.get_property('tagName')).lower() if await handle.get_property('tagName') else ''
        text_content = (await handle.text_content() or '').strip()
        
        # Heuristic: Don't skip if pointer cursor, clickable class, or data-action/link/click present
        is_likely_clickable = False
        try:
            style = await handle.get_attribute('style') or ''
            classes = await handle.get_attribute('class') or ''
            data_action = await handle.get_attribute('data-action')
            data_link = await handle.get_attribute('data-link')
            data_click = await handle.get_attribute('data-click')
            if (
                'cursor:pointer' in style or
                any(cls in classes for cls in ['clickable','card','product','tile','item','btn','link']) or
                data_action is not None or
                data_link is not None or
                data_click is not None
            ):
                is_likely_clickable = True
        except Exception:
            pass
        if not text_content and tag_name not in ('input', 'button', 'select', 'textarea') and not is_likely_clickable:
            return None
            
        # Get common attributes
        element_type = await handle.get_attribute('type') or ''
        element_id = await handle.get_attribute('id') or ''
        name = await handle.get_attribute('name') or ''
        placeholder = await handle.get_attribute('placeholder') or ''
        value = await handle.get_attribute('value') or ''
        
        # Get bounding box for coordinates
        box = await handle.bounding_box() or {}
        
        # Create element dictionary
        element = {
            'tag': tag_name,
            'text': text_content,
            'type': element_type,
            'id': element_id,
            'name': name,
            'placeholder': placeholder,
            'value': value,
            'selector': selector,
            'is_visible': await handle.is_visible(),
            'is_enabled': await handle.is_enabled(),
            'bounds': {
                'x': box.get('x', 0),
                'y': box.get('y', 0),
                'width': box.get('width', 0),
                'height': box.get('height', 0)
            }
        }
        
        # Add any additional attributes
        attributes = await handle.evaluate('''el => {
            const attrs = {};
            for (const {name, value} of el.attributes) {
                attrs[name] = value;
            }
            return attrs;
        }''')
        
        element['attributes'] = attributes
        
        return element
        
    except Exception as e:
        # Skip elements that cause errors
        return None


# Alias for backward compatibility
async def get_interactive_elements(page: Page) -> List[Dict]:
    """Find all interactive elements on the current page.
    
    Args:
        page: Playwright page object
        
    Returns:
        List of element dictionaries with properties
    """
    elements = []
    
    # Find all interactive elements
    selectors = [
        'a', 'button', 'input', 'select', 'textarea',
        '[role="button"]', '[role="link"]', '[role="checkbox"]',
        '[onclick]', '[onclick*=""]', '[tabindex]'
    ]
    
    for selector in selectors:
        found = await page.query_selector_all(selector)
        for element in found:
            try:
                # Skip if element is not visible
                if not await element.is_visible():
                    continue
                    
                # Get element properties
                tag = await element.evaluate('el => el.tagName')
                text = await element.inner_text() or ''
                attrs = await element.evaluate('''el => {
                    const attrs = {};
                    for (const attr of el.attributes) {
                        attrs[attr.name] = attr.value;
                    }
                    return attrs;
                }''')
                
                elements.append({
                    'tag': tag.lower(),
                    'text': text.strip(),
                    'attrs': attrs,
                })
            except Exception:
                continue
                
    return elements
