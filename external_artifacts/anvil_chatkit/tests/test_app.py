from anvil_chatkit import ChatKit, Persona


def test_register_and_lookup():
    kit = ChatKit()
    kit.register(Persona(slug="hello", name="Hello", system_prompt="hi"))
    assert kit.get("hello").name == "Hello"


def test_visible_filter():
    kit = ChatKit()
    kit.register(Persona(slug="a", name="A", system_prompt="", visible=True))
    kit.register(Persona(slug="b", name="B", system_prompt="", visible=False))
    visible = kit.visible()
    assert len(visible) == 1
    assert visible[0].slug == "a"


def test_duplicate_register_raises():
    import pytest
    kit = ChatKit()
    kit.register(Persona(slug="x", name="X", system_prompt=""))
    with pytest.raises(ValueError):
        kit.register(Persona(slug="x", name="X2", system_prompt=""))
