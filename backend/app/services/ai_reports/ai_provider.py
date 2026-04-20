"""AI provider abstraction — OpenAI is the concrete implementation in Phase 1."""
from __future__ import annotations

import json
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.security import decrypt_data
from app.models.database import AIProviderSettings

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Raised when the AI provider cannot produce a report."""


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate_report(self, system_prompt: str, user_prompt: str, response_schema: Dict[str, Any], model: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def test_connection(self, model: str) -> bool:
        ...


class OpenAIProvider(AIProvider):
    name = "openai"
    ALLOWED_MODELS = {"gpt-4o-mini", "gpt-4o", "gpt-4-turbo"}

    def __init__(self, api_key: str):
        if not api_key:
            raise AIProviderError("OpenAI API key missing")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise AIProviderError(
                "openai SDK is not installed — add 'openai>=1.0' to requirements.txt and restart."
            ) from exc
        self._OpenAI = OpenAI
        self._api_key = api_key

    def _client(self):
        return self._OpenAI(api_key=self._api_key, timeout=60.0)

    def _call_with_retry(self, fn, retries: int = 3):
        last: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return fn()
            except Exception as exc:
                last = exc
                delay = (2 ** attempt) + random.random()
                # Never log the prompt or key
                logger.warning("OpenAI call failed (attempt %d/%d): %s", attempt + 1, retries, type(exc).__name__)
                time.sleep(delay)
        raise AIProviderError(f"OpenAI call failed after {retries} attempts: {type(last).__name__}") from last

    def generate_report(self, system_prompt: str, user_prompt: str, response_schema: Dict[str, Any], model: str) -> Dict[str, Any]:
        if model not in self.ALLOWED_MODELS:
            model = "gpt-4o-mini"
        client = self._client()

        def _do():
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = resp.choices[0].message.content or "{}"
            usage = getattr(resp, "usage", None)
            return {
                "content": content,
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                    "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
                    "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
                },
                "model": model,
            }

        result = self._call_with_retry(_do)
        try:
            parsed = json.loads(result["content"])
        except json.JSONDecodeError as exc:
            raise AIProviderError("OpenAI returned malformed JSON") from exc
        if not isinstance(parsed, dict):
            raise AIProviderError("OpenAI response root is not a JSON object")
        return {"parsed": parsed, "usage": result["usage"], "model": result["model"]}

    def test_connection(self, model: str = "gpt-4o-mini") -> bool:
        if model not in self.ALLOWED_MODELS:
            model = "gpt-4o-mini"
        try:
            client = self._client()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Reply with exactly the word OK."},
                    {"role": "user", "content": "ping"},
                ],
                max_tokens=4,
                temperature=0.0,
            )
            reply = (resp.choices[0].message.content or "").strip().upper()
            return reply.startswith("OK")
        except Exception as exc:
            logger.warning("OpenAI test_connection failed: %s", type(exc).__name__)
            return False


def get_active_provider(db: Session) -> Optional[AIProvider]:
    """Return a configured provider or None if not set/enabled."""
    row = (
        db.query(AIProviderSettings)
        .filter(AIProviderSettings.enabled == True)  # noqa: E712
        .order_by(AIProviderSettings.id.asc())
        .first()
    )
    if not row or not row.api_key:
        return None
    try:
        key = decrypt_data(row.api_key)
    except Exception:
        logger.warning("AI provider stored key could not be decrypted")
        return None
    if row.provider == "openai":
        try:
            return OpenAIProvider(key)
        except AIProviderError as exc:
            logger.warning("Could not instantiate OpenAI provider: %s", exc)
            return None
    return None


def get_active_model(db: Session) -> str:
    row = (
        db.query(AIProviderSettings)
        .filter(AIProviderSettings.enabled == True)  # noqa: E712
        .order_by(AIProviderSettings.id.asc())
        .first()
    )
    if row and row.model:
        return row.model
    return "gpt-4o-mini"
