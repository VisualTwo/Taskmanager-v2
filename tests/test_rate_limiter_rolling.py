import time
import pytest
from infrastructure.rate_limiter import RateLimiter

def test_rate_limiter_blocks_after_5_failed_attempts_rolling():
    rl = RateLimiter(":memory:")
    ip = "1.2.3.4"
    now = int(time.time())
    # 4 fehlgeschlagene Versuche im Fenster
    for i in range(4):
        rl.add_attempt(ip)
    assert not rl.is_limited(ip)
    rl.add_attempt(ip)
    assert rl.is_limited(ip)
    # Erfolgreicher Login setzt nicht das Limit zurück, sondern wird nur dokumentiert
    rl.add_successful_login(ip)
    assert rl.is_limited(ip)  # Erfolgreiche Logins beeinflussen das Limit nicht
    rl.clear_attempts(ip)
    assert not rl.is_limited(ip)
    rl.close()

def test_successful_login_tracking():
    rl = RateLimiter(":memory:")
    ip = "5.6.7.8"
    now = int(time.time())
    # Füge 5 erfolgreiche Logins hinzu
    for i in range(5):
        rl.add_successful_login(ip)
        time.sleep(0.01)  # Zeitunterschied für Sortierung
    last = rl.get_last_successful_logins(ip)
    assert len(last) == 3
    rl.close()
