def greet(name: str) -> str:
    """Return greet message for the given name.

    Args:
        name: Name to greet. Empty or whitespace-only names return "hello".

    Returns:
        Formatted greeting message.
    """
    if not name or not name.strip():
        return "hello"
    return f"hello, {name.strip()}"
