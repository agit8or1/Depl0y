"""Rate limiting middleware"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status
import time
import uuid
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Auth endpoints that receive the stricter rate limit
_AUTH_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/2fa/login",
    "/api/v1/auth/refresh",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory token-bucket rate limiting middleware.

    - Default: RATE_LIMIT_DEFAULT requests/minute per IP
    - Auth endpoints: RATE_LIMIT_AUTH requests/minute per IP (stricter)
    - Adds X-Request-ID and X-Response-Time headers to every response
    - Cleans up stale IP entries every ~5 minutes to bound memory usage
    """

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # Sliding-window buckets: {ip: [timestamp, ...]}
        self.requests: dict = defaultdict(list)
        self.auth_requests: dict = defaultdict(list)
        self._last_cleanup = time.time()
        logger.info(
            f"Rate limiting initialised: default={requests_per_minute}/min, "
            f"auth={self._auth_rpm()}/min"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _auth_rpm(self) -> int:
        """Return the auth-endpoint rate limit from settings (lazy import)."""
        try:
            from app.core.config import settings
            return settings.RATE_LIMIT_AUTH
        except Exception:
            return 10

    def _enabled(self) -> bool:
        try:
            from app.core.config import settings
            return settings.RATE_LIMIT_ENABLED
        except Exception:
            return True

    def _cleanup_stale(self, current_time: float):
        """Periodically remove IPs with no recent requests to avoid unbounded growth."""
        if current_time - self._last_cleanup < 300:  # every 5 minutes
            return
        cutoff = current_time - 60
        stale_ips = [ip for ip, ts in self.requests.items() if not any(t > cutoff for t in ts)]
        for ip in stale_ips:
            del self.requests[ip]
        stale_auth = [ip for ip, ts in self.auth_requests.items() if not any(t > cutoff for t in ts)]
        for ip in stale_auth:
            del self.auth_requests[ip]
        self._last_cleanup = current_time

    # ------------------------------------------------------------------
    # Middleware dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Attach request-id so downstream handlers can read it
        request.state.request_id = request_id

        # Rate-limit check (skip if disabled)
        if self._enabled():
            client_ip = request.client.host if request.client else "unknown"
            current_time = time.time()
            cutoff_time = current_time - 60
            self._cleanup_stale(current_time)

            is_auth = request.url.path in _AUTH_PATHS

            if is_auth:
                auth_rpm = self._auth_rpm()
                self.auth_requests[client_ip] = [
                    t for t in self.auth_requests[client_ip] if t > cutoff_time
                ]
                if len(self.auth_requests[client_ip]) >= auth_rpm:
                    logger.warning(
                        f"Auth rate limit exceeded for {client_ip} "
                        f"({len(self.auth_requests[client_ip])}/{auth_rpm} rpm)"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": "Too many requests. Please try again later.",
                            "retry_after": 60,
                        },
                        headers={
                            "X-Request-ID": request_id,
                            "Retry-After": "60",
                        },
                    )
                self.auth_requests[client_ip].append(current_time)
            else:
                self.requests[client_ip] = [
                    t for t in self.requests[client_ip] if t > cutoff_time
                ]
                if len(self.requests[client_ip]) >= self.requests_per_minute:
                    logger.warning(
                        f"Rate limit exceeded for {client_ip} "
                        f"({len(self.requests[client_ip])}/{self.requests_per_minute} rpm)"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": "Too many requests. Please slow down.",
                            "retry_after": 60,
                        },
                        headers={
                            "X-Request-ID": request_id,
                            "Retry-After": "60",
                        },
                    )
                self.requests[client_ip].append(current_time)

        response = await call_next(request)

        # Inject diagnostic headers into every response
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        return response
