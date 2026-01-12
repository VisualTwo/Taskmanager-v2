import time
from fastapi import Request
from infrastructure.rate_limiter import RateLimiter

rate_limiter = RateLimiter()

async def check_rate_limit(request: Request) -> bool:
    ip = request.client.host
    return rate_limiter.is_limited(ip)

async def add_login_attempt(request: Request):
    ip = request.client.host
    rate_limiter.add_attempt(ip)

async def clear_login_attempts(request: Request):
    ip = request.client.host
    rate_limiter.clear_attempts(ip)
