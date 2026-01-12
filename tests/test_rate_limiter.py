import time
import pytest
from infrastructure.rate_limiter import RateLimiter

def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter(":memory:")
    ip = "1.2.3.4"
    # 5 allowed attempts
    for _ in range(5):
        assert not rl.is_limited(ip)
        rl.add_attempt(ip)
    # 6th should be blocked
    assert rl.is_limited(ip)
    rl.clear_attempts(ip)
    assert not rl.is_limited(ip)
    rl.close()

def test_rate_limiter_window_expires():
    rl = RateLimiter(":memory:")
    ip = "5.6.7.8"
    now = int(time.time())
    # Add 5 attempts in the past, outside window
    old = now - 301
    for _ in range(5):
        rl.conn.execute("INSERT INTO login_attempts (ip, timestamp) VALUES (?, ?)", (ip, old))
    rl.conn.commit()
    assert not rl.is_limited(ip)
    rl.close()
