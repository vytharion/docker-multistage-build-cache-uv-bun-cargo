SERVICE_NAME = "api"
WORKSPACE_TOOL = "uv"


def greet(name: str) -> str:
    return f"hello, {name}, from the {SERVICE_NAME} service"


def workspace_anchor() -> str:
    return WORKSPACE_TOOL
