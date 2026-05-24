"""HTTP client for the RAG-system API.

Wraps every endpoint described in RAG_SYSTEM_API.md. The client caches the
JWT obtained from ``POST /auth/key`` and re-authenticates transparently on
401 responses.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RAGClientError(RuntimeError):
    """Raised when the RAG system returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RAGClient:
    def __init__(
        self,
        base_url: str,
        secret: str,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.timeout = timeout
        self._client = client or httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        )
        self._api_key: str | None = None
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ---- auth ----
    async def authenticate(self, force: bool = False) -> str:
        if self._api_key and not force:
            return self._api_key
        if not self.secret:
            raise RAGClientError("RAG_API_SECRET not configured")
        url = f"{self.base_url}/auth/key"
        logger.info("event=rag.auth.start url=%s", url)
        response = await self._client.post(url, json={"secret": self.secret})
        if response.is_error:
            raise RAGClientError(
                f"auth failed: {response.text[:200]}", response.status_code
            )
        data = response.json()
        key = data.get("api-key") or data.get("api_key") or data.get("token")
        if not key:
            raise RAGClientError("no api-key in /auth/key response")
        self._api_key = key
        logger.info("event=rag.auth.done")
        return key

    async def _headers(self) -> dict[str, str]:
        key = await self.authenticate()
        return {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        auth_required: bool = True,
        _retry_on_401: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = await self._headers() if auth_required else {}
        response = await self._client.request(
            method, url, json=json, params=params, headers=headers
        )
        if response.status_code == 401 and auth_required and _retry_on_401:
            logger.info("event=rag.401 reauth")
            self._api_key = None
            return await self._request(
                method,
                path,
                json=json,
                params=params,
                auth_required=auth_required,
                _retry_on_401=False,
            )
        if response.is_error:
            raise RAGClientError(
                f"{method} {path} -> {response.status_code}: {response.text[:200]}",
                response.status_code,
            )
        if not response.content:
            return None
        return response.json()

    # ---- health (public) ----
    async def health(self) -> dict:
        return await self._request("GET", "/system/health", auth_required=False)

    # ---- staging-area resources ----
    async def list_resource_types(self) -> dict:
        return await self._request("GET", "/staging-area/resorces/type")

    async def create_resource_type(self, name: str) -> dict:
        return await self._request(
            "POST", "/staging-area/resorces/type", json={"name": name}
        )

    async def list_recommendation_types(self) -> dict:
        return await self._request("GET", "/staging-area/recommendations/type")

    async def create_recommendation_type(self, name: str) -> dict:
        return await self._request(
            "POST", "/staging-area/recommendations/type", json={"name": name}
        )

    async def upload_resource(
        self,
        resource_type: str,
        text: str,
        url: str | None = None,
        title: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"resource_type": resource_type, "text": text}
        if url is not None:
            payload["url"] = url
        if title is not None:
            payload["title"] = title
        return await self._request("POST", "/staging-area", json=payload)

    async def get_resource(self, resource_id: int) -> dict:
        return await self._request("GET", f"/staging-area/{resource_id}")

    async def import_email(self, mautic_id: int | None = None) -> dict:
        payload: dict[str, Any] = {}
        if mautic_id is not None:
            payload["id"] = mautic_id
        return await self._request("POST", "/staging-area/email", json=payload)

    # ---- vector db ----
    async def vector_db_status(self) -> dict:
        return await self._request("GET", "/vector-db/status")

    async def resource_status(
        self, resource_id: int, create_embedding: bool = False
    ) -> dict:
        return await self._request(
            "GET",
            f"/vector-db/resource-status/{resource_id}",
            params={"create_embedding": str(create_embedding).lower()},
        )

    # ---- recommendations ----
    async def generate_recommendation(self, lead_id: str, lead_type: str) -> dict:
        return await self._request(
            "POST",
            "/recommendations/generate",
            json={"lead_id": lead_id, "type": lead_type},
        )

    async def recommendation_status(self, token: str) -> dict:
        return await self._request("GET", f"/recommendations/status/{token}")

    async def get_recommendations(self, lead_id: str) -> dict:
        return await self._request("GET", f"/recommendations/{lead_id}")

    async def get_lead_actions(self, lead_id: str) -> dict:
        return await self._request("GET", f"/recommendations/actions/{lead_id}")

    async def get_lead_tasks(self, lead_id: str) -> dict:
        return await self._request("GET", f"/recommendations/tasks/{lead_id}")

    # ---- prompts ----
    async def get_prompt(self, lead_type: str) -> dict:
        return await self._request("GET", "/prompt", params={"lead_type": lead_type})

    async def update_prompt(self, lead_type: str, prompt: str) -> dict:
        return await self._request(
            "PUT",
            "/prompt",
            json={"lead_type": lead_type, "prompt": prompt},
        )

    # ---- mautic ----
    async def create_mautic_field(self, name: str, field_type: str = "text") -> dict:
        return await self._request(
            "POST", "/mautic/field", json={"name": name, "type": field_type}
        )

    async def update_mautic_field(self, lead_id: str, field: str, value: Any) -> dict:
        return await self._request(
            "PATCH",
            "/mautic/field",
            json={"lead_id": lead_id, "field": field, "value": value},
        )

    async def check_mautic_contact(self, email: str) -> dict:
        return await self._request(
            "GET", "/mautic/contact/check", params={"email": email}
        )
