from pathlib import Path
import os
import time
import uuid
from collections import defaultdict
from fastapi import FastAPI, UploadFile, File, Depends, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from src.generation.conversation import Conversation
from src.generation.context_builder import load_facts, extract_topics
from src.fetch_github import fetch_github_readmes
from src import session_store
from src.admin_auth import login, verify_token, revoke_token


app = FastAPI()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, Conversation] = {}


class AskRequest(BaseModel):
    session_id: str | None = None
    query: str


class AskResponse(BaseModel):
    session_id: str
    response: str
    suggestions: list[str]
    summary: str


class LoginRequest(BaseModel):
    password: str


_cached_facts = None
_cached_topics = None

_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300

_chat_attempts: dict[str, list[float]] = defaultdict(list)
MAX_CHAT_ATTEMPTS = 10
CHAT_WINDOW = 60


def _get_client_ip(request_obj: Request) -> str:
    forwarded = request_obj.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request_obj.client.host


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_WINDOW]
    if len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS:
        return False
    _login_attempts[ip].append(now)
    return True


def _check_chat_rate_limit(ip: str) -> bool:
    now = time.time()
    _chat_attempts[ip] = [t for t in _chat_attempts[ip] if now - t < CHAT_WINDOW]
    if len(_chat_attempts[ip]) >= MAX_CHAT_ATTEMPTS:
        return False
    _chat_attempts[ip].append(now)
    return True


def _load_facts_and_topics():
    global _cached_facts, _cached_topics
    if _cached_facts is not None:
        return _cached_facts, _cached_topics

    facts = load_facts()
    _cached_facts = facts
    _cached_topics = extract_topics(facts)
    return facts, _cached_topics


@app.post("/chat", response_model=AskResponse)
async def chat(request: AskRequest, request_obj: Request):
    ip = _get_client_ip(request_obj)
    if not _check_chat_rate_limit(ip):
        return Response(status_code=429, content="trop de messages, réessayez plus tard")
    session_id = request.session_id or str(uuid.uuid4())
    is_new = session_id not in sessions

    if is_new:
        _load_facts_and_topics()
        sessions[session_id] = Conversation()
        session_store.create_session(session_id)

    conv = sessions[session_id]

    session_store.append_message(session_id, "user", request.query)

    result = await conv.ask(request.query)

    session_store.append_message(session_id, "bot", result["response"], {
        "suggestions": result["suggestions"],
    })
    session_store.update_summary(session_id, conv.summary)

    return {
        "response": result["response"],
        "summary": conv.summary,
        "suggestions": result["suggestions"],
        "session_id": session_id,
    }


# ── Admin auth ───────────────────────────────────────────────────

@app.post("/admin/login")
async def admin_login(request: LoginRequest, response: Response, request_obj: Request):
    ip = _get_client_ip(request_obj)
    if not _check_rate_limit(ip):
        return Response(status_code=429, content="too many attempts, try later")
    token = login(request.password)
    if not token:
        return {"error": "wrong password"}
    secure = not os.getenv("DEV")
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=1800,
    )
    return {"ok": True}


@app.post("/admin/logout")
async def admin_logout(response: Response, admin_token: str = Cookie(None)):
    if admin_token:
        revoke_token(admin_token)
    response.delete_cookie("admin_token")
    return {"ok": True}


# ── Admin endpoints (protected) ──────────────────────────────────

@app.get("/admin/sessions")
async def admin_list_sessions(_=Depends(verify_token)):
    return session_store.list_sessions()


@app.get("/admin/sessions/{session_id}")
async def admin_get_session(session_id: str, _=Depends(verify_token)):
    data = session_store.get_session(session_id)
    if not data:
        return {"error": "session not found"}
    return data


@app.delete("/admin/sessions/{session_id}")
async def admin_delete_session(session_id: str, _=Depends(verify_token)):
    if session_id in sessions:
        del sessions[session_id]
    deleted = session_store.delete_session(session_id)
    return {"deleted": deleted}


@app.get("/admin/stats")
async def admin_stats(_=Depends(verify_token)):
    return session_store.get_stats()


DATA_DIR = Path("data")


@app.get("/admin/data")
async def admin_list_data_files(_=Depends(verify_token)):
    files = []
    for f in sorted(DATA_DIR.glob("*.json")):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        })
    return files


MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@app.post("/admin/data")
async def admin_upload_data(file: UploadFile = File(...), _=Depends(verify_token)):
    safe_name = Path(file.filename).name
    if not safe_name.endswith(".json") or safe_name.startswith("."):
        return {"error": "only .json files allowed"}
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return {"error": "file too large (max 10MB)"}
    dest = DATA_DIR / safe_name
    dest.write_bytes(content)
    global _cached_facts, _cached_topics
    _cached_facts = None
    _cached_topics = None
    return {"uploaded": safe_name}


@app.delete("/admin/data/{filename}")
async def admin_delete_data(filename: str, _=Depends(verify_token)):
    safe_name = Path(filename).name
    target = DATA_DIR / safe_name
    if not target.resolve().is_relative_to(DATA_DIR.resolve()):
        return {"error": "invalid filename"}
    if target.exists() and target.suffix == ".json":
        target.unlink()
        global _cached_facts, _cached_topics
        _cached_facts = None
        _cached_topics = None
        return {"deleted": safe_name}
    return {"error": "file not found"}


@app.post("/admin/refresh-github")
async def admin_refresh_github(_=Depends(verify_token)):
    global _cached_facts, _cached_topics
    result = fetch_github_readmes()
    _cached_facts = None
    _cached_topics = None
    return result


# ── Frontend catch-all ───────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = (FRONTEND_DIR / full_path).resolve()
    if not file_path.is_relative_to(FRONTEND_DIR.resolve()):
        return Response(status_code=403, content="forbidden")
    if file_path.is_file():
        cache = "no-cache" if not full_path.startswith("assets/") else "public, max-age=31536000, immutable"
        return FileResponse(file_path, headers={"Cache-Control": cache})
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
