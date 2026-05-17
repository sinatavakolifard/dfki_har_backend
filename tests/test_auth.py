async def test_health_is_unauthenticated(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_protected_endpoint_requires_key(client):
    r = await client.get("/v1/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 401


async def test_protected_endpoint_rejects_wrong_key(client):
    r = await client.get(
        "/v1/users/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": "nope"},
    )
    assert r.status_code == 401
