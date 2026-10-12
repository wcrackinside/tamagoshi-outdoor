import json
import pytest
import app.main as main
from tests.test_mission_engine import VALID, fake_ollama


@pytest.fixture(autouse=True)
def clean_jobs():
    main.JOBS.clear()
    yield
    main.JOBS.clear()


def test_job_returns_immediately_and_then_holds_the_gemma_result(client, monkeypatch):
    monkeypatch.setattr(main, "call_ollama", fake_ollama(json.dumps(VALID)))
    started = client.post("/missions/jobs", json={"minutes": 10, "language": "es"})
    assert started.status_code == 202
    job = started.json()
    assert job["status"] == "running" and job["job_id"]
    body = client.get(f"/missions/jobs/{job['job_id']}").json()
    assert body["status"] == "done"
    result = body["result"]
    assert result["source"] == "gemma" and result["fallback_reason"] is None
    assert [m["title"] for m in result["missions"]] == [m["title"] for m in VALID["missions"]]
    stored = {m["id"] for m in client.get("/missions").json()["missions"]}
    assert {m["id"] for m in result["missions"]} <= stored


def test_job_falls_back_to_labeled_demo_when_ollama_is_down(client, monkeypatch):
    monkeypatch.setattr(main, "call_ollama", fake_ollama(exc=main.httpx.ConnectError("offline")))
    job = client.post("/missions/jobs", json={"language": "en"}).json()
    result = client.get(f"/missions/jobs/{job['job_id']}").json()["result"]
    assert result["source"] == "demo" and result["fallback_reason"] == "ai_unavailable"


def test_job_reports_error_when_generation_crashes(client, monkeypatch):
    async def boom(req):
        raise RuntimeError("disk full")
    monkeypatch.setattr(main, "_generate", boom)
    job = client.post("/missions/jobs", json={}).json()
    body = client.get(f"/missions/jobs/{job['job_id']}").json()
    assert body["status"] == "error" and body["result"] is None


def test_second_job_is_rejected_while_one_is_running(client):
    main.JOBS["busy"] = {"status": "running", "created": main.time.time(), "result": None}
    assert client.post("/missions/jobs", json={}).status_code == 429


def test_unknown_job_is_404(client):
    assert client.get("/missions/jobs/does-not-exist").status_code == 404


def test_finished_jobs_expire(client, monkeypatch):
    monkeypatch.setattr(main, "call_ollama", fake_ollama(json.dumps(VALID)))
    main.JOBS["old"] = {"status": "done", "created": main.time.time() - main.JOB_TTL_SECONDS - 1, "result": None}
    client.post("/missions/jobs", json={})
    assert "old" not in main.JOBS


def test_job_rejects_invalid_input(client):
    assert client.post("/missions/jobs", json={"language": "fr"}).status_code == 422
    assert main.JOBS == {}
