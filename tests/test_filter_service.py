import pytest
from services.filter_service import _norm_s, _norm_lower, _iter_lower

def test_norm_s():
    assert _norm_s(" Test ") == "Test"
    assert _norm_s(None) == ""
    assert _norm_s("") == ""

def test_norm_lower():
    assert _norm_lower("Test") == "test"
    assert _norm_lower(None) == ""

def test_iter_lower():
    assert _iter_lower(["A", "B"]) == ["a", "b"]
    assert _iter_lower(None) == []
    assert _iter_lower([]) == []

# Negativ-Tests

def test_iter_lower_invalid():
    assert _iter_lower([None, "A"]) == ["a"]
