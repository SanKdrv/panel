"""Test the RAG HTTP client with respx mocking."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.services.rag_client import RAGClient, RAGClientError


@pytest.fixture
def base_url():
    return "http://rag-test"


@pytest.mark.asyncio
async def test_authenticate_caches_key(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            route = router.post("/auth/key").mock(
                return_value=httpx.Response(200, json={"api-key": "k1"})
            )
            k1 = await client.authenticate()
            k2 = await client.authenticate()
        assert k1 == k2 == "k1"
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_authenticate_missing_secret(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="", client=http)
        with pytest.raises(RAGClientError):
            await client.authenticate()


@pytest.mark.asyncio
async def test_authenticate_bad_response(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            router.post("/auth/key").mock(return_value=httpx.Response(500, text="oops"))
            with pytest.raises(RAGClientError):
                await client.authenticate()


@pytest.mark.asyncio
async def test_health_public(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            router.get("/system/health").mock(
                return_value=httpx.Response(200, json={"status": "healthy"})
            )
            data = await client.health()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_upload_resource_sends_payload(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            router.post("/auth/key").mock(
                return_value=httpx.Response(200, json={"api-key": "k"})
            )
            route = router.post("/staging-area").mock(
                return_value=httpx.Response(200, json={"resource_id": 1, "status": "queued"})
            )
            data = await client.upload_resource("FAQ", "hello")
        assert data["resource_id"] == 1
        import json
        sent = json.loads(route.calls.last.request.read())
        assert sent == {"resource_type": "FAQ", "text": "hello"}


@pytest.mark.asyncio
async def test_reauth_on_401(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            router.post("/auth/key").mock(
                side_effect=[
                    httpx.Response(200, json={"api-key": "k1"}),
                    httpx.Response(200, json={"api-key": "k2"}),
                ]
            )
            router.get("/vector-db/status").mock(
                side_effect=[
                    httpx.Response(401, text="expired"),
                    httpx.Response(200, json={"status": "ready"}),
                ]
            )
            data = await client.vector_db_status()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_get_prompt_query_param(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            router.post("/auth/key").mock(
                return_value=httpx.Response(200, json={"api-key": "k"})
            )
            route = router.get("/prompt", params={"lead_type": "cold"}).mock(
                return_value=httpx.Response(200, json={"lead_type": "cold", "prompt": "x"})
            )
            data = await client.get_prompt("cold")
        assert data["prompt"] == "x"
        assert route.called


@pytest.mark.asyncio
async def test_update_prompt(base_url):
    async with httpx.AsyncClient() as http:
        client = RAGClient(base_url, secret="s", client=http)
        with respx.mock(base_url=base_url) as router:
            router.post("/auth/key").mock(
                return_value=httpx.Response(200, json={"api-key": "k"})
            )
            router.put("/prompt").mock(
                return_value=httpx.Response(200, json={"lead_type": "warm", "prompt": "new"})
            )
            data = await client.update_prompt("warm", "new")
        assert data["prompt"] == "new"
