"""Тонкая обёртка над Prometheus HTTP API (query/query_range)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PrometheusClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def query_range(
        self,
        query: str,
        start: float,
        end: float,
        step: float,
    ) -> list[dict[str, Any]]:
        """Возвращает список серий: [{"metric": {...}, "values": [[ts, "val"], ...]}]."""
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            r = await http.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": step,
                },
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "success":
                raise RuntimeError(f"prometheus error: {data}")
            return data["data"]["result"]

    async def query(self, query: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            r = await http.get(
                f"{self.base_url}/api/v1/query",
                params={"query": query},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "success":
                raise RuntimeError(f"prometheus error: {data}")
            return data["data"]["result"]
