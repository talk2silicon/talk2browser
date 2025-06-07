"""Tests for tools module."""

def test_tool_registry_initialization(tool_registry):
    """Test that the tool registry initializes with base tools."""
    tools = tool_registry.list_tools()
    assert len(tools) > 0
    assert any(tool["name"] == "navigate" for tool in tools)


def test_register_tool(tool_registry):
    """Test registering a new tool."""
    def test_func():
        return "test"
        
    tool_registry.register_tool(
        name="test_tool",
        func=test_func,
        description="A test tool",
        parameters={"type": "object", "properties": {}}
    )
    
    tool = tool_registry.get_tool("test_tool")
    assert tool is not None
    assert tool["function"]() == "test"
