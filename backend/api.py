import asyncio
import json
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
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from src import session_store
from src.admin_auth import login, verify_token, revoke_token
from src.fetch_github import fetch_github_readmes
from src.generation import precompute
from src.generation.context_builder import validate_facts_data
from src.generation.conversation import Conversation


logger = logging.getLogger(__name__)

app = FastAPI()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

sessions: dict[str, Conversation] = {}


class AskRequest(BaseModel):
    session_id: str | None = None
    query: str
    target_fact_id: str | None = None
    target_detail_id: str | None = None
    target_tag: str | None = None

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


class DerivedUpdate(BaseModel):
    content: dict


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
            conv.summary_ids = list(stored.get("summary_ids", []))
            conv.prune_summary_ids(stored.get("summaries", []))
            sessions[session_id] = conv
        else:
            sessions[session_id] = Conversation()
            session_store.create_session(session_id, user_agent=user_agent)

    conv = sessions[session_id]

    try:
        result = await conv.ask(
            request.query,
            request.target_fact_id,
            request.target_detail_id,
            request.target_tag,
        )
    except Exception:
        logger.exception("chat: échec de l'appel LLM (session %s)", session_id)
        return JSONResponse(
            {"detail": "Le service de réponse est momentanément indisponible, réessayez dans un instant."},
            status_code=503,
        )

    session_store.append_message(session_id, "user", request.query)
    turn_summary = result.get("turn_summary", "")

    session_store.record_response(
        session_id,
        result["response"],
        {"suggestions": result["suggestions"]},
        turn_summary,
        list(conv.essentials_done),
        list(conv.details_done),
        list(conv.summary_ids),
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

_derived_jobs: dict[str, dict] = {}


def _derived_status(name: str) -> dict:
    job = _derived_jobs.get(name)
    if job:
        return dict(job)
    dest = precompute.derived_path(name)
    if dest.is_file():
        try:
            data = json.loads(dest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        return {
            "status": "ok",
            "error": "",
            "fact_count": data.get("fact_count", 0),
            "tag_count": data.get("tag_count", 0),
            "generated_at": data.get("edited_at") or data.get("generated_at") or dest.stat().st_mtime,
        }
    return {"status": "none", "error": "", "fact_count": 0, "tag_count": 0, "generated_at": 0}


async def _run_precompute(name: str) -> None:
    _derived_jobs[name] = {
        "status": "running",
        "error": "",
        "fact_count": 0,
        "tag_count": 0,
        "generated_at": time.time(),
    }
    try:
        dest = await precompute.generate_for_source(DATA_DIR / name)
        data = json.loads(dest.read_text(encoding="utf-8"))
        _derived_jobs[name] = {
            "status": "ok",
            "error": "",
            "fact_count": data.get("fact_count", 0),
            "tag_count": data.get("tag_count", 0),
            "generated_at": data.get("generated_at", time.time()),
        }
    except Exception as exc:
        logger.exception("precompute failed for %s", name)
        _derived_jobs[name] = {
            "status": "error",
            "error": str(exc),
            "fact_count": 0,
            "tag_count": 0,
            "generated_at": time.time(),
        }


def _start_precompute(name: str) -> None:
    if name == "sessions.json":
        return
    asyncio.create_task(_run_precompute(name))


@app.get("/admin/data")
async def admin_list_data_files(_=Depends(verify_token)):
    files = []
    for f in sorted(DATA_DIR.glob("*.json")):
        if f.name == "sessions.json":
            continue
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
            "derived": _derived_status(f.name),
        })
    return files


@app.post("/admin/data/{filename}/recompute")
async def admin_recompute_data(filename: str, _=Depends(verify_token)):
    target = _resolve_data_file(filename)
    if target is None:
        return {"error": "file not found"}
    job = _derived_jobs.get(target.name)
    if job and job.get("status") == "running":
        return {"error": "génération déjà en cours"}
    _start_precompute(target.name)
    return {"started": target.name}


def _resolve_data_file(filename: str) -> Path | None:
    safe_name = Path(filename).name
    target = DATA_DIR / safe_name
    if not target.resolve().is_relative_to(DATA_DIR.resolve()):
        return None
    if not target.is_file() or target.suffix != ".json":
        return None
    return target


@app.get("/admin/data/{filename}/derived")
async def admin_get_derived_file(filename: str, _=Depends(verify_token)):
    if Path(filename).name == "sessions.json":
        return {"error": "file not found"}
    path = precompute.derived_path(Path(filename).name)
    if not path.is_file():
        return {"error": "derived not found"}
    raw = path.read_text(encoding="utf-8")
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        return {"name": path.name, "content": None, "raw": raw, "error": "invalid json"}
    return {"name": path.name, "source": Path(filename).name, "content": content, "raw": raw}


@app.put("/admin/data/{filename}/derived")
async def admin_update_derived(filename: str, payload: DerivedUpdate, _=Depends(verify_token)):
    if Path(filename).name == "sessions.json":
        return {"error": "file not found"}
    target = _resolve_data_file(filename)
    if target is None:
        return {"error": "file not found"}
    job = _derived_jobs.get(target.name)
    if job and job.get("status") == "running":
        return {"error": "génération en cours, réessayez à la fin"}
    try:
        dest = precompute.save_derived(target.name, payload.content)
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    data = json.loads(dest.read_text(encoding="utf-8"))
    _derived_jobs.pop(target.name, None)
    return {
        "saved": target.name,
        "fact_count": data.get("fact_count", 0),
        "edited_at": data.get("edited_at", 0),
    }


@app.get("/admin/data/{filename}")
async def admin_get_data_file(filename: str, _=Depends(verify_token)):
    if Path(filename).name == "sessions.json":
        return {"error": "file not found"}
    target = _resolve_data_file(filename)
    if target is None:
        return {"error": "file not found"}
    raw = target.read_text(encoding="utf-8")
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        return {"name": target.name, "content": None, "raw": raw, "error": "invalid json"}
    return {"name": target.name, "content": content, "raw": raw}


MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@app.post("/admin/data")
async def admin_upload_data(file: UploadFile = File(...), _=Depends(verify_token)):
    safe_name = Path(file.filename).name
    if not safe_name.endswith(".json") or safe_name.startswith(".") or safe_name == "sessions.json":
        return JSONResponse({"error": "nom de fichier refusé (.json uniquement, sessions.json réservé)"}, status_code=400)
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse({"error": "file too large (max 10MB)"}, status_code=413)
    try:
        problem = validate_facts_data(json.loads(content))
    except (json.JSONDecodeError, UnicodeDecodeError):
        problem = "JSON invalide"
    if problem:
        return JSONResponse({"error": f"fichier refusé : {problem}"}, status_code=400)
    dest = DATA_DIR / safe_name
    if not dest.resolve().is_relative_to(DATA_DIR.resolve()):
        return {"error": "invalid filename"}
    dest.write_bytes(content)
    _start_precompute(safe_name)
    return {"uploaded": safe_name}


@app.delete("/admin/data/{filename}")
async def admin_delete_data(filename: str, _=Depends(verify_token)):
    safe_name = Path(filename).name
    target = DATA_DIR / safe_name
    if not target.resolve().is_relative_to(DATA_DIR.resolve()):
        return {"error": "invalid filename"}
    if target.exists() and target.suffix == ".json":
        target.unlink()
        _derived_jobs.pop(safe_name, None)
        derived = precompute.derived_path(safe_name)
        if derived.is_file():
            derived.unlink()
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
