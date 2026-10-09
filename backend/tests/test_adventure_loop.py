import os, socket, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
import app.main as main
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def offline_ai(monkeypatch):
    async def unreachable(prompt):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(main, "call_ollama", unreachable)


def generate(client, minutes=10, language="en"):
    res = client.post("/missions/generate", json={"minutes": minutes, "language": language})
    assert res.status_code == 200
    return res.json()["missions"]


def test_full_loop_generate_complete_journal(client, offline_ai):
    before = client.get("/journal").json()["total_points"]
    mission = generate(client, minutes=15)[0]
    assert mission["points"] == 60 and mission["completed_at"] is None

    res = client.post(f"/missions/{mission['id']}/complete", json={"reflection": "  A red door I never noticed.  "})
    assert res.json() == {"completed": True, "points": 60}

    journal = client.get("/journal").json()
    assert journal["total_points"] == before + 60
    entry = journal["entries"][0]
    assert entry["title"] == mission["title"]
    assert entry["reflection"] == "A red door I never noticed."

    listed = {m["id"]: m for m in client.get("/missions").json()["missions"]}
    assert listed[mission["id"]]["completed_at"] is not None


def test_reflection_is_optional(client, offline_ai):
    mission = generate(client)[0]
    assert client.post(f"/missions/{mission['id']}/complete", json={}).status_code == 200
    assert client.get("/journal").json()["entries"][0]["reflection"] == ""


def test_second_completion_is_rejected_without_extra_points(client, offline_ai):
    mission = generate(client)[0]
    assert client.post(f"/missions/{mission['id']}/complete", json={"reflection": "first"}).status_code == 200
    total = client.get("/journal").json()["total_points"]

    second = client.post(f"/missions/{mission['id']}/complete", json={"reflection": "again"})
    assert second.status_code == 409
    assert second.json()["detail"] == "Already completed"

    journal = client.get("/journal").json()
    assert journal["total_points"] == total
    assert [e["reflection"] for e in journal["entries"] if e["title"] == mission["title"]].count("again") == 0


def test_concurrent_completions_award_points_once(client, offline_ai):
    mission = generate(client)[0]
    total = client.get("/journal").json()["total_points"]

    def attempt(_):
        return TestClient(app).post(f"/missions/{mission['id']}/complete", json={"reflection": "race"}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(attempt, range(8)))

    assert sorted(codes) == [200] + [409] * 7
    assert client.get("/journal").json()["total_points"] == total + mission["points"]


def test_completion_validation(client, offline_ai):
    mission = generate(client)[0]
    assert client.post(f"/missions/{mission['id']}/complete", json={"reflection": "x" * 501}).status_code == 422
    assert client.post("/missions/not-a-number/complete", json={}).status_code == 422
    assert client.post("/missions/999999/complete", json={}).status_code == 404


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(db_path, port):
    env = {**os.environ, "DB_PATH": str(db_path), "OLLAMA_URL": "http://127.0.0.1:9", "OLLAMA_TIMEOUT": "2"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("backend did not start")


def stop_server(proc):
    proc.terminate()
    proc.wait(timeout=10)


def test_sqlite_persists_across_server_restarts():
    db_path = Path(tempfile.mkdtemp(prefix="tamagoshi-restart-")) / "outdoor.db"
    port = free_port()
    base = f"http://127.0.0.1:{port}"

    proc = start_server(db_path, port)
    try:
        missions = httpx.post(f"{base}/missions/generate", json={"minutes": 5, "language": "es"}, timeout=30).json()["missions"]
        assert httpx.post(f"{base}/missions/{missions[0]['id']}/complete", json={"reflection": "Vi un colibrí"}).status_code == 200
    finally:
        stop_server(proc)

    proc = start_server(db_path, port)
    try:
        journal = httpx.get(f"{base}/journal").json()
        assert journal["total_points"] == 20
        assert journal["entries"][0]["reflection"] == "Vi un colibrí"
        assert len(httpx.get(f"{base}/missions").json()["missions"]) == 3
        assert httpx.post(f"{base}/missions/{missions[0]['id']}/complete", json={}).status_code == 409
    finally:
        stop_server(proc)
