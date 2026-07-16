"""Unit tests for scripts/_e2e_greet.py (Chat→CCC E2E)."""

from _e2e_greet import greet


def test_greet_with_name():
    assert greet("Ada") == "hello, Ada"


def test_greet_empty():
    assert greet("") == "hello"
    assert greet("  ") == "hello"
