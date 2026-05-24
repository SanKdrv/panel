def test_create_field(client, auth_headers, fake_rag):
    r = client.post(
        "/api/mautic/field",
        headers=auth_headers,
        json={"name": "Recommendation", "type": "textarea"},
    )
    assert r.status_code == 200
    fake_rag.create_mautic_field.assert_awaited_with("Recommendation", "textarea")


def test_update_field(client, auth_headers, fake_rag):
    r = client.patch(
        "/api/mautic/field",
        headers=auth_headers,
        json={"lead_id": "1", "field": "rec", "value": "hi"},
    )
    assert r.status_code == 200
    fake_rag.update_mautic_field.assert_awaited_with("1", "rec", "hi")


def test_check_contact(client, auth_headers, fake_rag):
    r = client.get(
        "/api/mautic/contact/check?email=a%40b.com", headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["unique"] is True
    fake_rag.check_mautic_contact.assert_awaited_with("a@b.com")
