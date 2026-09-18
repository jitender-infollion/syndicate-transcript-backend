def _ingest_headers(api_key: str = "test-ingest-key") -> dict:
    return {"x-api-key": api_key}


def test_publish_requires_api_key(client):
    resp = client.post("/api/internal/transcripts", json={})
    assert resp.status_code == 401


def test_publish_stores_about_expert_and_returns_it_in_public_responses(client, monkeypatch, engine):
    monkeypatch.setenv("SYNDICATE_INBOUND_API_KEY", "test-ingest-key")

    payload = {
        "fk_session": 123456,
        "fk_expert": 9001,
        "expert_name": "Sarah Mitchell",
        "designation": "VP of Revenue Operations",
        "years_of_experience": 12,
        "about_expert": "12+ years leading enterprise revenue teams.",
        "topic": "Enterprise AI Integration",
        "domains": ["Enterprise SaaS"],
        "geographies": ["North America"],
        "preview": "A short preview of the conversation.",
        "final_transcript": {"url": "s3://bucket/key.pdf", "type": "pdf"},
        "key_insights": ["Budgets are shifting toward consumption pricing"],
        "price": 49,
        "currency": "USD",
        "is_active": True,
    }

    resp = client.post("/api/internal/transcripts", json=payload, headers=_ingest_headers())
    assert resp.status_code == 200, resp.text
    transcript_id = resp.json()["id"]

    detail_resp = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["data"]["expert"]["aboutExpert"] == "12+ years leading enterprise revenue teams."


def test_republish_updates_about_expert(client, monkeypatch, engine):
    monkeypatch.setenv("SYNDICATE_INBOUND_API_KEY", "test-ingest-key")

    base_payload = {
        "fk_session": 777,
        "fk_expert": 9002,
        "about_expert": "Original bio.",
        "preview": "preview",
        "final_transcript": {"url": "s3://bucket/key.pdf", "type": "pdf"},
        "price": 10,
    }

    first = client.post("/api/internal/transcripts", json=base_payload, headers=_ingest_headers())
    assert first.status_code == 200, first.text
    transcript_id = first.json()["id"]

    updated_payload = {**base_payload, "about_expert": "Updated bio."}
    second = client.post("/api/internal/transcripts", json=updated_payload, headers=_ingest_headers())
    assert second.status_code == 200, second.text
    assert second.json()["id"] == transcript_id  # same row, upserted on fk_session

    detail_resp = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert detail_resp.json()["data"]["expert"]["aboutExpert"] == "Updated bio."
