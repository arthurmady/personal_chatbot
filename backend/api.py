from pathlib import Path
import uuid
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from langchain_core.documents import Document

from src.generation.conversation import Conversation
from src.generation.context_builder import extract_topics
from src.fetch_github import fetch_github_readmes
from src import session_store
from src.admin_auth import login, verify_token


app = FastAPI()

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


_cached_docs = None
_cached_topics = None


def _load_all_docs_and_topics():
    global _cached_docs, _cached_topics
    if _cached_docs is not None:
        return _cached_docs, _cached_topics

    md_files = sorted(Path("data").glob("*.md"))
    blocks = []
    topics: list[str] = []
    for file in md_files:
        raw = file.read_text(encoding="utf-8")
        blocks.append(raw)
        topics.extend(extract_topics(raw))

    full_text = "\n\n---\n\n".join(blocks)
    _cached_docs = [Document(page_content=full_text)]
    _cached_topics = topics
    return _cached_docs, topics


@app.post("/chat", response_model=AskResponse)
async def chat(request: AskRequest):
    session_id = request.session_id or str(uuid.uuid4())
    is_new = session_id not in sessions

    if is_new:
        all_docs, topics = _load_all_docs_and_topics()
        sessions[session_id] = Conversation(all_docs, topics)
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


@app.post("/refresh-github")
async def refresh_github():
    global _cached_docs, _cached_topics
    result = fetch_github_readmes()
    _cached_docs = None
    _cached_topics = None
    return result


# ── Admin auth ───────────────────────────────────────────────────

@app.post("/admin/login")
async def admin_login(request: LoginRequest):
    token = login(request.password)
    if not token:
        return {"error": "wrong password"}
    return {"token": token}


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
    for f in sorted(DATA_DIR.glob("*.md")):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        })
    return files


@app.post("/admin/data")
async def admin_upload_data(file: UploadFile = File(...), _=Depends(verify_token)):
    dest = DATA_DIR / file.name
    content = await file.read()
    dest.write_bytes(content)
    global _cached_docs, _cached_topics
    _cached_docs = None
    _cached_topics = None
    return {"uploaded": file.name}


@app.delete("/admin/data/{filename}")
async def admin_delete_data(filename: str, _=Depends(verify_token)):
    target = DATA_DIR / filename
    if target.exists() and target.suffix == ".md":
        target.unlink()
        global _cached_docs, _cached_topics
        _cached_docs = None
        _cached_topics = None
        return {"deleted": filename}
    return {"error": "file not found"}


@app.post("/admin/refresh-github")
async def admin_refresh_github(_=Depends(verify_token)):
    return await refresh_github()


# ── Frontend catch-all ───────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        cache = "no-cache" if not full_path.startswith("assets/") else "public, max-age=31536000, immutable"
        return FileResponse(file_path, headers={"Cache-Control": cache})
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
