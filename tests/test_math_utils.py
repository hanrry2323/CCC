from math_utils import add


def test_add():
    assert add(2, 3) == 5


def test_add_zero():
    assert add(0, 0) == 0
    assert add(0, 5) == 5


def test_add_negative():
    assert add(-1, -2) == -3
    assert add(-4, 7) == 3


def test_add_float():
    assert add(1.5, 2.25) == 3.75