import os, tempfile
os.environ["DB_PATH"]=tempfile.mktemp(suffix=".db")
from fastapi.testclient import TestClient
from app.main import app, fallback, safe

def test_health():
    assert TestClient(app).get("/health").json()["ok"]

def test_demo_catalog():
    assert len(fallback(5,"es"))==3
    assert not safe("Go to private property")

def test_missing_mission():
    assert TestClient(app).post("/missions/9999/complete",json={"reflection":"ok"}).status_code==404
