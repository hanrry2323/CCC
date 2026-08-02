"""
Prompt building service

Handles prompt construction and formatting logic for LLM interactions.
"""

__all__ = ["build_prompt", "format_message"]


# Placeholder for prompt construction utilities
def build_prompt(template: str, **context: dict) -> str:
    """Build a prompt from a template and context."""
    return template.format(**context)


def format_message(role: str, content: str) -> str:
    """Format a message for LLM communication."""
    return f"{role}: {content}"
