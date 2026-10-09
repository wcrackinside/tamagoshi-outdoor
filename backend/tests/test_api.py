from app.main import fallback, safe

def test_health(client):
    assert client.get("/health").json()["ok"]

def test_demo_catalog():
    assert len(fallback(5,"es"))==3
    assert not safe("Go to private property")

def test_missing_mission(client):
    assert client.post("/missions/9999/complete",json={"reflection":"ok"}).status_code==404
