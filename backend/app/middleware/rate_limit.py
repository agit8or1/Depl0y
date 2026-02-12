"""Rate limiting middleware"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status
import time
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware"""

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)  # {ip: [timestamp1, timestamp2, ...]}
        self.login_requests = defaultdict(list)  # Separate tracking for login
        logger.info(f"Rate limiting initialized: {requests_per_minute}/minute")

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        logger.debug(f"RateLimitMiddleware checking: {client_ip} -> {request.url.path}")

        # Clean old entries (older than 1 minute)
        cutoff_time = current_time - 60

        # Check if this is a login endpoint
        is_login = request.url.path == "/api/v1/auth/login" and request.method == "POST"

        if is_login:
            # Strict rate limit for login: 5 per minute
            self.login_requests[client_ip] = [
                t for t in self.login_requests[client_ip] if t > cutoff_time
            ]

            if len(self.login_requests[client_ip]) >= 5:
                logger.warning(f"Rate limit exceeded for login from {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many login attempts. Please try again later.",
                        "retry_after": 60
                    }
                )

            self.login_requests[client_ip].append(current_time)
        else:
            # General rate limit: 100 per minute
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > cutoff_time
            ]

            if len(self.requests[client_ip]) >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many requests. Please slow down.",
                        "retry_after": 60
                    }
                )

            self.requests[client_ip].append(current_time)

        response = await call_next(request)
        return response
