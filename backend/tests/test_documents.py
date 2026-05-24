def test_list_resource_types(client, auth_headers):
    r = client.get("/api/documents/resource-types", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["resource_types"][0]["name"] == "FAQ"


def test_create_resource_type(client, auth_headers, fake_rag):
    r = client.post(
        "/api/documents/resource-types",
        headers=auth_headers,
        json={"name": "Prices"},
    )
    assert r.status_code == 200
    fake_rag.create_resource_type.assert_awaited_with("Prices")


def test_upload_resource(client, auth_headers, fake_rag):
    payload = {"resource_type": "FAQ", "text": "Hello world"}
    r = client.post("/api/documents", headers=auth_headers, json=payload)
    assert r.status_code == 200
    assert r.json()["resource_id"] == 42
    fake_rag.upload_resource.assert_awaited()


def test_import_email_bulk(client, auth_headers, fake_rag):
    r = client.post(
        "/api/documents/import/email", headers=auth_headers, json={}
    )
    assert r.status_code == 200
    fake_rag.import_email.assert_awaited_with(mautic_id=None)


def test_import_email_single(client, auth_headers, fake_rag):
    r = client.post(
        "/api/documents/import/email", headers=auth_headers, json={"id": 17}
    )
    assert r.status_code == 200
    fake_rag.import_email.assert_awaited_with(mautic_id=17)


def test_vector_db_status(client, auth_headers):
    r = client.get("/api/documents/vector-db/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_documents_require_auth(client):
    assert client.get("/api/documents/resource-types").status_code == 401
    assert client.post("/api/documents", json={}).status_code == 401
