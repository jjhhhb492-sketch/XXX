import os, time, httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

KEY = os.getenv("FOOTBALL_API_KEY", "")
BASE = "https://api.football-data.org/v4"
app = FastAPI()
cache = {}
SDB = os.getenv("SPORTSDB_KEY", "123")

async def get(path, params=None, ttl=300):
    k = (path, tuple(sorted((params or {}).items())))
    now = time.time()
    if k in cache and now - cache[k][0] < ttl:
        return cache[k][1]
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(BASE + path, params=params, headers={"X-Auth-Token": KEY})
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    cache[k] = (now, r.json())
    return cache[k][1]

@app.get("/api/live")
async def live():
    return await get("/matches", {"status": "IN_PLAY,PAUSED"}, ttl=30)

@app.get("/api/{code}/matches")
async def matches(code: str, status: str = "FINISHED"):
    d = await get(f"/competitions/{code}/matches", {"status": status}, ttl=120)
    m = d["matches"]
    m = m[-30:][::-1] if status == "FINISHED" else m[:30]
    return {"matches": m}

@app.get("/api/{code}/standings")
async def standings(code: str):
    return await get(f"/competitions/{code}/standings")

@app.get("/api/{code}/scorers")
async def scorers(code: str):
    return await get(f"/competitions/{code}/scorers", {"limit": 20})

@app.get("/api/match/{mid}")
async def match(mid: int):
    return await get(f"/matches/{mid}", ttl=30)

@app.get("/api/player")
async def player(name: str):
    k = ("sdb", name.lower())
    now = time.time()
    if k in cache and now - cache[k][0] < 86400:
        return cache[k][1]
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"https://www.thesportsdb.com/api/v1/json/{SDB}/searchplayers.php", params={"p": name})
    if r.status_code != 200:
        return {"players": []}
    ps = r.json().get("player") or []
    out = [{"name": p.get("strPlayer"), "team": p.get("strTeam"), "pos": p.get("strPosition"),
            "nat": p.get("strNationality"), "h": p.get("strHeight"),
            "img": p.get("strCutout") or p.get("strThumb") or p.get("strRender")}
           for p in ps if p.get("strSport") == "Soccer"][:12]
    cache[k] = (now, {"players": out})
    return cache[k][1]

@app.get("/")
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))

