def test_import_find_interactive_elements():
    from talk2browser.browser.element_utils import find_interactive_elements

    assert callable(find_interactive_elements)
