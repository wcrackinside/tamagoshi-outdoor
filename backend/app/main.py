import os, json, sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="Tamagoshi Outdoor")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "outdoor.db"))

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS missions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT NOT NULL,
            minutes INTEGER NOT NULL, points INTEGER NOT NULL,
            source TEXT NOT NULL, completed_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS journal(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER NOT NULL UNIQUE, reflection TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        )""")
init()

class GenerateRequest(BaseModel):
    interests: str = Field(default="nature, curiosity", max_length=200)
    minutes: int = Field(default=5, ge=5, le=30)
    language: str = Field(default="es", pattern="^(es|en)$")

class CompleteRequest(BaseModel):
    reflection: str = Field(default="", max_length=500)

def fallback(minutes, lang):
    if lang == "en":
        return [
            {"title":"Three unnoticed details","description":"Step outside somewhere safe and notice a color, a sound and a small detail you normally miss."},
            {"title":"Sky reset","description":"Spend a few minutes outside looking at the sky and noticing how the light changes."},
            {"title":"Urban nature","description":"Walk on a familiar public route and observe a plant or tree you haven't paid attention to."},
        ]
    return [
        {"title":"Tres detalles invisibles","description":"Sal a un espacio seguro y descubre un color, un sonido y un detalle que normalmente ignoras."},
        {"title":"Pausa bajo el cielo","description":"Dedica unos minutos a observar el cielo desde un lugar público y seguro."},
        {"title":"Naturaleza urbana","description":"Recorre un camino público conocido y observa un árbol o planta que no habías notado."},
    ]

def safe(text):
    banned = ["trespass", "private property", "cross traffic", "climb a roof", "propiedad privada", "cruza el tráfico", "sube al techo"]
    return not any(term in text.lower() for term in banned)

async def generate_ai(req):
    prompt = f"""You design safe, accessible outdoor micro-adventures for adults. Respond ONLY with JSON: {{"missions":[{{"title":"...","description":"..."}}]}}. Exactly 3 missions, in language {req.language}. Duration {req.minutes} minutes each. Interests: {req.interests}. Only public, safe locations. Never require GPS, risky activity, spending money, private property or proof of completion. Keep each description under 180 characters."""
    async with httpx.AsyncClient(timeout=12) as client:
        res = await client.post(os.getenv("OLLAMA_URL","http://localhost:11434").rstrip("/") + "/api/generate",
            json={"model":os.getenv("OLLAMA_MODEL","gemma3:4b"),"prompt":prompt,"stream":False,"format":"json"})
        res.raise_for_status()
        raw = res.json()["response"]
        parsed = json.loads(raw)
        items = parsed["missions"]
        if not isinstance(items,list) or len(items)!=3:
            raise ValueError("Expected three missions")
        out=[]
        for item in items:
            title,desc=item["title"],item["description"]
            if not isinstance(title,str) or not isinstance(desc,str) or not (3<=len(title)<=90 and 12<=len(desc)<=240) or not safe(title+" "+desc):
                raise ValueError("Invalid mission")
            out.append({"title":title,"description":desc})
        return out

@app.get("/health")
def health():
    return {"ok":True}

@app.post("/missions/generate")
async def generate(req: GenerateRequest):
    source="gemma"
    try:
        missions=await generate_ai(req)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        source="demo"
        missions=fallback(req.minutes,req.language)
    result=[]
    with db() as conn:
        for m in missions:
            points=req.minutes*4
            cur=conn.execute("INSERT INTO missions(title,description,minutes,points,source) VALUES(?,?,?,?,?)",
                (m["title"],m["description"],req.minutes,points,source))
            result.append({"id":cur.lastrowid,**m,"minutes":req.minutes,"points":points,"source":source,"completed_at":None})
    return {"missions":result,"source":source}

@app.get("/missions")
def missions():
    with db() as conn:
        rows=conn.execute("SELECT * FROM missions ORDER BY id DESC LIMIT 100").fetchall()
    return {"missions":[dict(r) for r in rows]}

@app.post("/missions/{mission_id}/complete")
def complete(mission_id:int, body:CompleteRequest):
    now=datetime.now(timezone.utc).isoformat()
    with db() as conn:
        row=conn.execute("SELECT * FROM missions WHERE id=?",(mission_id,)).fetchone()
        if not row: raise HTTPException(404,"Mission not found")
        if row["completed_at"]: raise HTTPException(409,"Already completed")
        conn.execute("UPDATE missions SET completed_at=? WHERE id=?",(now,mission_id))
        conn.execute("INSERT INTO journal(mission_id,reflection,created_at) VALUES(?,?,?)",
            (mission_id,body.reflection.strip(),now))
    return {"completed":True,"points":row["points"]}

@app.get("/journal")
def journal():
    with db() as conn:
        entries=conn.execute("""SELECT j.id,j.reflection,j.created_at,m.title,m.points
            FROM journal j JOIN missions m ON j.mission_id=m.id ORDER BY j.id DESC""").fetchall()
    return {"entries":[dict(x) for x in entries],"total_points":sum(x["points"] for x in entries)}
