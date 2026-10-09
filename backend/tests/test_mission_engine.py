import json
import httpx
import pytest
import app.main as main
from app.main import GenerateRequest, build_prompt, fallback, parse_ai_output, safe

VALID = {"missions": [
    {"title": "Tres detalles invisibles", "description": "Busca un color, un sonido y una textura en una plaza cercana."},
    {"title": "Pausa bajo el cielo", "description": "Observa cómo cambian las nubes durante unos minutos en un parque."},
    {"title": "Hoja curiosa", "description": "Encuentra una hoja con una forma inusual en un sendero público."},
]}

def with_missions(**overrides):
    data = json.loads(json.dumps(VALID))
    data["missions"][0].update(overrides)
    return json.dumps(data)

def fake_ollama(raw=None, exc=None):
    async def _call(prompt):
        if exc:
            raise exc
        return raw
    return _call

def test_parse_valid_output():
    missions = parse_ai_output(json.dumps(VALID))
    assert [m["title"] for m in missions] == [m["title"] for m in VALID["missions"]]

@pytest.mark.parametrize("wrap", ["```json\n{}\n```", "Here you go:\n{}\nEnjoy!", "  {}  "])
def test_parse_extracts_json_and_ignores_extra_fields(wrap):
    data = json.loads(json.dumps(VALID))
    data["missions"][0]["emoji"] = "🌳"
    missions = parse_ai_output(wrap.replace("{}", json.dumps(data, indent=2)))
    assert missions[0] == {"title": VALID["missions"][0]["title"], "description": VALID["missions"][0]["description"]}

def test_parse_rejects_missing_comma_seen_from_gemma():
    raw = '{"missions":[{"title":"Shadow Music"\n "description":"Seek out a shaded area in a park."}]}'
    with pytest.raises(ValueError):
        parse_ai_output(raw)

@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "not json at all",
    "[]",
    "{}",
    '{"missions": "three"}',
    json.dumps({"missions": VALID["missions"][:2]}),
    json.dumps({"missions": VALID["missions"] + [VALID["missions"][0]]}),
    with_missions(title=42),
    with_missions(description=None),
    with_missions(title="ok"),
    with_missions(description="x" * 241),
    with_missions(title="Pausa bajo el cielo"),
    with_missions(description="Climb a roof to watch the sunset over the city skyline."),
    with_missions(description="Entra a una propiedad privada para ver el jardín escondido."),
    with_missions(description='Observe sparrows in a park. A great intro to birdwatching! “}]} ,{"\n\t\t},{"title'),
    with_missions(description="Reflect on architecture and nature.”}]} 0x0000000000000000"),
    with_missions(title="<b>Bold</b> walk"),
], ids=[
    "empty", "blank", "plain-text", "json-list", "missing-key", "missions-not-list", "too-few", "too-many",
    "title-not-string", "description-null", "title-too-short", "description-too-long", "duplicate-titles",
    "unsafe-en", "unsafe-es", "leaked-json", "trailing-junk", "markup",
])
def test_parse_rejects_invalid_output(raw):
    with pytest.raises(ValueError):
        parse_ai_output(raw)

def test_parse_rejects_non_string():
    with pytest.raises(ValueError):
        parse_ai_output(None)

def test_safe_allows_ordinary_wording():
    assert safe("Pay attention to the birds in a public park.")
    assert safe("Comprende el ritmo de la ciudad desde una banca.")

def test_fallback_missions_pass_own_validation():
    for lang in ("es", "en"):
        assert parse_ai_output(json.dumps({"missions": fallback(5, lang)}))

@pytest.mark.parametrize("lang,name", [("es", "Spanish"), ("en", "English")])
def test_prompt_requests_language(lang, name):
    prompt = build_prompt(GenerateRequest(language=lang, minutes=10, interests="birds"))
    assert f"written entirely in {name}" in prompt
    assert "10 minutes" in prompt

def test_generate_uses_gemma_when_valid(client, monkeypatch):
    monkeypatch.setattr(main, "call_ollama", fake_ollama(json.dumps(VALID)))
    body = client.post("/missions/generate", json={"minutes": 10, "language": "es"}).json()
    assert body["source"] == "gemma"
    assert body["fallback_reason"] is None
    assert all(m["source"] == "gemma" and m["points"] == 40 for m in body["missions"])

@pytest.mark.parametrize("raw", ["garbage", json.dumps({"missions": []}), with_missions(description="Climb a roof now please ok")])
def test_generate_labels_invalid_output_as_demo(client, monkeypatch, raw):
    monkeypatch.setattr(main, "call_ollama", fake_ollama(raw))
    body = client.post("/missions/generate", json={"minutes": 5, "language": "en"}).json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "ai_invalid_output"
    assert [m["title"] for m in body["missions"]] == [m["title"] for m in fallback(5, "en")]
    assert all(m["source"] == "demo" for m in body["missions"])

def test_generate_retries_once_after_invalid_output(client, monkeypatch):
    replies = iter(["garbage", json.dumps(VALID)])
    async def flaky(prompt):
        return next(replies)
    monkeypatch.setattr(main, "call_ollama", flaky)
    assert client.post("/missions/generate", json={}).json()["source"] == "gemma"

def test_generate_stops_after_configured_attempts(client, monkeypatch):
    calls = []
    async def always_bad(prompt):
        calls.append(prompt)
        return "garbage"
    monkeypatch.setattr(main, "call_ollama", always_bad)
    monkeypatch.setenv("AI_ATTEMPTS", "3")
    assert client.post("/missions/generate", json={}).json()["fallback_reason"] == "ai_invalid_output"
    assert len(calls) == 3

@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
def test_generate_labels_unavailable_ai_as_demo(client, monkeypatch, exc):
    monkeypatch.setattr(main, "call_ollama", fake_ollama(exc=exc))
    body = client.post("/missions/generate", json={"minutes": 5, "language": "es"}).json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "ai_unavailable"
    assert len(body["missions"]) == 3

def test_generate_handles_unexpected_ollama_payload(client, monkeypatch):
    async def bad_payload(prompt):
        return {"missions": "not a string"}
    monkeypatch.setattr(main, "call_ollama", bad_payload)
    assert client.post("/missions/generate", json={}).json()["fallback_reason"] == "ai_invalid_output"

@pytest.mark.parametrize("payload", [{"language": "fr"}, {"minutes": 2}, {"minutes": 31}, {"interests": "x" * 201}])
def test_generate_rejects_bad_requests(client, payload):
    assert client.post("/missions/generate", json=payload).status_code == 422
