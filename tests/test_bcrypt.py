import bcrypt
import pytest

def test_bcrypt_password_check():
    password = "geheim123"
    hash_ = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    # Richtige Eingabe
    assert bcrypt.checkpw(password.encode("utf-8"), hash_)
    # Falsche Eingabe
    assert not bcrypt.checkpw("falsch".encode("utf-8"), hash_)
