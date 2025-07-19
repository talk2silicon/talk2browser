import pytest
import asyncio
from talk2browser.tools.browser_tools import get_screenshot, generate_pdf_from_html
from talk2browser.services.action_service import ActionService

@pytest.mark.asyncio
async def test_pdf_generation_with_screenshots():
    # Simulate browser actions and screenshots
    # (In a real test, you would drive the browser, here we simulate for demo)
    # Capture two screenshots (simulate)
    path1 = await get_screenshot()
    path2 = await get_screenshot(selector="#main-content")

    # Retrieve all screenshots from the action recorder
    screenshots = await get_screenshot(mode="history")
    assert path1 in screenshots and path2 in screenshots

    # Generate dummy HTML
    html_content = """
    <html><body><h1>PDF Test</h1><div id='main-content'>Main Content</div></body></html>
    """
    # Generate PDF with screenshots
    pdf_path = await generate_pdf_from_html(html=html_content, screens=screenshots)
    assert pdf_path.endswith(".pdf")
    print(f"PDF generated at: {pdf_path}")
