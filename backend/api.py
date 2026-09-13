from pathlib import Path
import uuid
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from langchain_core.documents import Document

from src.generation.conversation import Conversation
from src.generation.context_builder import extract_topics
from src.fetch_github import fetch_github_readmes


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

    if session_id not in sessions:
        all_docs, topics = _load_all_docs_and_topics()
        sessions[session_id] = Conversation(all_docs, topics)

    conv = sessions[session_id]

    result = await conv.ask(request.query)

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


FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        cache = "no-cache" if not full_path.startswith("assets/") else "public, max-age=31536000, immutable"
        return FileResponse(file_path, headers={"Cache-Control": cache})
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
