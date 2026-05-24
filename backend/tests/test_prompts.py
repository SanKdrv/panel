def test_list_prompts(client, auth_headers, fake_rag):
    r = client.get("/api/prompts", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    types = {p["lead_type"] for p in body}
    assert {"cold", "warm", "hot", "after_sale"}.issubset(types)


def test_get_prompt(client, auth_headers):
    r = client.get("/api/prompts/cold", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["lead_type"] == "cold"


def test_update_prompt(client, auth_headers, fake_rag):
    r = client.put(
        "/api/prompts",
        headers=auth_headers,
        json={"lead_type": "warm", "prompt": "new prompt"},
    )
    assert r.status_code == 200
    assert r.json()["prompt"] == "new prompt"
    fake_rag.update_prompt.assert_awaited_with("warm", "new prompt")


def test_update_prompt_invalid_lead_type(client, auth_headers):
    r = client.put(
        "/api/prompts",
        headers=auth_headers,
        json={"lead_type": "bogus", "prompt": "x"},
    )
    assert r.status_code == 422
