from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from .exceptions import FetchError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass(slots=True)
class HttpClient:
    delay: float = 0.2
    timeout: float = 20.0
    retries: int = 3
    backoff_factor: float = 1.5
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
    session: requests.Session = field(default_factory=requests.Session)
    _last_request_at: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.delay = max(0.0, float(self.delay))
        self.timeout = max(1.0, float(self.timeout))
        self.retries = max(0, int(self.retries))
        self.backoff_factor = max(1.0, float(self.backoff_factor))
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            }
        )

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _respect_delay(self) -> None:
        if self._last_request_at is None or self.delay <= 0:
            return
        remaining = self.delay - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._respect_delay()
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    timeout=(self.timeout, self.timeout),
                    allow_redirects=True,
                )
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                wait = self.backoff_factor * (2**attempt)
                logger.warning(
                    "请求失败，%.1f 秒后重试（%d/%d）：%s",
                    wait,
                    attempt + 1,
                    self.retries,
                    url,
                )
                time.sleep(wait)
                continue

            if 200 <= response.status_code < 400:
                return response

            retryable = response.status_code in RETRYABLE_STATUS_CODES
            if retryable and attempt < self.retries:
                wait = self._retry_wait(response, attempt)
                logger.warning(
                    "HTTP %d，%.1f 秒后重试（%d/%d）：%s",
                    response.status_code,
                    wait,
                    attempt + 1,
                    self.retries,
                    url,
                )
                time.sleep(wait)
                continue

            raise FetchError(f"HTTP {response.status_code}: {url}")

        detail = f"：{last_error}" if last_error else ""
        raise FetchError(f"请求失败，已重试 {self.retries} 次{detail}: {url}")

    def _retry_wait(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "").strip()
        if retry_after.isdigit():
            return min(float(retry_after), 60.0)
        if retry_after:
            try:
                target = parsedate_to_datetime(retry_after).timestamp()
                return max(0.0, min(target - time.time(), 60.0))
            except (TypeError, ValueError, OverflowError):
                pass
        return self.backoff_factor * (2**attempt)

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        response = self.request("GET", url, headers=headers, params=params)
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.request("GET", url, headers=headers, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            preview = response.text[:200].replace("\n", " ")
            raise FetchError(f"接口未返回 JSON：{preview}") from exc
        if not isinstance(payload, dict):
            raise FetchError("接口返回格式不是 JSON 对象")
        return payload
