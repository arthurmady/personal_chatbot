import logging
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI, Depends, Request, Cookie, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from src import session_store
from src.admin_auth import login, verify_token, revoke_token
from src.fetch_github import fetch_github_readmes
from src.generation.conversation import Conversation


app = FastAPI()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

sessions: dict[str, Conversation] = {}


class AskRequest(BaseModel):
    session_id: str | None = None
    query: str
    target_fact_id: str | None = None
    target_detail_id: str | None = None

    def model_post_init(self, __context):
        if len(self.query) > 2000:
            raise ValueError("question trop longue (max 2000 caractères)")


class AskResponse(BaseModel):
    session_id: str
    response: str
    suggestions: list[dict]
    summary: str


class LoginRequest(BaseModel):
    password: str


_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300

_chat_attempts: dict[str, list[float]] = defaultdict(list)
MAX_CHAT_ATTEMPTS = 10
CHAT_WINDOW = 60


def _get_client_ip(request_obj: Request) -> str:
    return request_obj.client.host


def _check_rate_limit(store: dict[str, list[float]], ip: str, window: int, max_attempts: int) -> bool:
    now = time.time()
    store[ip] = [t for t in store[ip] if now - t < window]
    if len(store[ip]) >= max_attempts:
        return False
    store[ip].append(now)
    return True


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    data = session_store.get_session(session_id)
    if not data:
        return Response(status_code=404, content="session not found")
    return {
        "session_id": session_id,
        "messages": [
            {"role": m["role"], "content": m["content"]}
            for m in data.get("messages", [])
        ],
        "summaries": data.get("summaries", []),
        "user_agent": data.get("user_agent", ""),
    }


@app.post("/chat", response_model=AskResponse)
async def chat(request: AskRequest, request_obj: Request):
    ip = _get_client_ip(request_obj)
    if not _check_rate_limit(_chat_attempts, ip, CHAT_WINDOW, MAX_CHAT_ATTEMPTS):
        return Response(status_code=429, content="trop de messages, réessayez plus tard")
    session_id = request.session_id or str(uuid.uuid4())
    is_new = session_id not in sessions

    user_agent = request_obj.headers.get("user-agent") or ""

    if is_new:
        stored = session_store.get_session(session_id)
        if stored:
            conv = Conversation()
            conv.essentials_done = set(stored.get("essentials_done", []))
            conv.details_done = set(stored.get("details_done", []))
            sessions[session_id] = conv
        else:
            sessions[session_id] = Conversation()
            session_store.create_session(session_id, user_agent=user_agent)

    conv = sessions[session_id]

    session_store.append_message(session_id, "user", request.query)

    result = await conv.ask(request.query, request.target_fact_id, request.target_detail_id)
    turn_summary = result.get("turn_summary", "")

    session_store.record_response(
        session_id,
        result["response"],
        {"suggestions": result["suggestions"]},
        turn_summary,
        list(conv.essentials_done),
        list(conv.details_done),
    )

    return {
        "response": result["response"],
        "summary": turn_summary,
        "suggestions": result["suggestions"],
        "session_id": session_id,
    }


# ── Admin auth ───────────────────────────────────────────────────

@app.post("/admin/login")
async def admin_login(request: LoginRequest, response: Response, request_obj: Request):
    ip = _get_client_ip(request_obj)
    if not _check_rate_limit(_login_attempts, ip, LOGIN_WINDOW, MAX_LOGIN_ATTEMPTS):
        return Response(status_code=429, content="too many attempts, try later")
    token = login(request.password)
    if not token:
        return Response(status_code=401, content="wrong password")
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
    if not dest.resolve().is_relative_to(DATA_DIR.resolve()):
        return {"error": "invalid filename"}
    dest.write_bytes(content)
    return {"uploaded": safe_name}


@app.delete("/admin/data/{filename}")
async def admin_delete_data(filename: str, _=Depends(verify_token)):
    safe_name = Path(filename).name
    target = DATA_DIR / safe_name
    if not target.resolve().is_relative_to(DATA_DIR.resolve()):
        return {"error": "invalid filename"}
    if target.exists() and target.suffix == ".json":
        target.unlink()
        return {"deleted": safe_name}
    return {"error": "file not found"}


@app.post("/admin/refresh-github")
async def admin_refresh_github(_=Depends(verify_token)):
    return fetch_github_readmes()


# ── Static pages ────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/politique-confidentialite.html")
async def serve_privacy_policy():
    return FileResponse(STATIC_DIR / "politique-confidentialite.html", headers={"Cache-Control": "no-cache"})


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
