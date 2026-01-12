import pytest
from utils.text_helpers import unescape_description

def test_unescape_description_positive():
    assert unescape_description("A\\nB\\,C") == "A\nB,C"
    assert unescape_description("Zeile1\\nZeile2\\,Komma") == "Zeile1\nZeile2,Komma"
    assert unescape_description("") == ""
    assert unescape_description(None) == ""

def test_unescape_description_negative():
    # Echte Zeilenumbrüche und Kommas bleiben erhalten
    assert unescape_description("A\nB,C") == "A\nB,C"
    # Doppelte Backslashes bleiben erhalten (werden nicht zu Zeilenumbruch)
    assert unescape_description(r"A\\nB") == r"A\\nB"
