from api import greet, workspace_anchor


def test_greet_includes_target_name():
    assert "hello, world" in greet("world")


def test_greet_mentions_api_service():
    assert "api service" in greet("world")


def test_workspace_anchor_identifies_uv():
    assert workspace_anchor() == "uv"
