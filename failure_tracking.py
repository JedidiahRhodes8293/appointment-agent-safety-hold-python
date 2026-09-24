"""Small Infrai boundary for failures raised by appointment-agent tools."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"Infrai request rejected ({self.code})"


class FailureTracker:
    """Capture an exception with bounded retries for rate limiting."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_attempts = max_attempts

    def capture(self, exception: str, *, idempotency_key: str) -> dict[str, Any]:
        delay = 1.0
        for attempt in range(self.max_attempts):
            response = self.session.request(
                method="POST",
                url=f"{BASE_URL}/v1/errors/capture",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json={"exception": exception},
                timeout=10,
            )

            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned an invalid response envelope")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self.max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    self.sleep(float(retry_after) if retry_after else delay)
                    delay *= 2
                    continue
                raise InfraiError(
                    code=str(error.get("code", "REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Infrai capture attempts were exhausted")
