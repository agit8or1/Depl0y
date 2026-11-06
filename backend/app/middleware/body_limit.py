"""Request-body size caps for endpoints that accept data without a user login.

FastAPI reads and parses the whole body before any dependency runs, so the
cap has to sit in front of the app. A declared Content-Length over the limit
is refused at once; a chunked body is counted as it streams and refused as
soon as it passes the limit.
"""
import json

from fastapi import HTTPException


class _TooLarge(HTTPException):
    # An HTTPException so FastAPI's body reader re-raises it as a 413 instead
    # of wrapping it in a generic "error parsing the body" 400.
    def __init__(self, limit: int):
        super().__init__(status_code=413, detail=f"Request body too large (limit {limit} bytes)")


class BodySizeLimitMiddleware:
    def __init__(self, app, limits: dict):
        self.app = app
        self.limits = limits  # {path: max bytes}

    async def __call__(self, scope, receive, send):
        limit = self.limits.get(scope.get("path")) if scope["type"] == "http" else None
        if limit is None:
            return await self.app(scope, receive, send)

        for name, value in scope.get("headers") or []:
            if name == b"content-length":
                try:
                    if int(value) > limit:
                        return await self._reject(send, limit)
                except ValueError:
                    return await self._reject(send, limit, status=400, detail="Invalid Content-Length")

        seen = 0
        started = False

        async def limited_receive():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge(limit)
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send, limit, status=413, detail=None):
        body = json.dumps({"detail": detail or f"Request body too large (limit {limit} bytes)"}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
