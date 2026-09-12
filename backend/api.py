from pathlib import Path
import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.generation.conversation import Conversation
from src.generation.context_builder import extract_topics
from src.ingestion.ingest import ingest


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

    all_docs = []
    topics: list[str] = []
    for file in Path("data").glob("*"):
        if file.is_file():
            file_path = str(file.resolve())
            docs_file = ingest(file_path)
            all_docs.extend(docs_file)
            if file.suffix.lower() == ".md":
                raw_text = file.read_text(encoding="utf-8")
                topics.extend(extract_topics(raw_text))

    _cached_docs = all_docs
    _cached_topics = topics
    return all_docs, topics


@app.post("/chat", response_model=AskResponse)
async def chat(request: AskRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id or str(uuid.uuid4())
    is_new_session = session_id not in sessions

    if is_new_session:
        all_docs, topics = _load_all_docs_and_topics()
        sessions[session_id] = Conversation(all_docs, topics)

    conv = sessions[session_id]

    result = await conv.ask(request.query)

    for cle, valeur in conv.topics_covered.items():
        print(cle, ":", valeur)

    return {
        "response": result["response"],
        "summary": conv.summary,
        "suggestions": result["suggestions"],
        "session_id": session_id,
    }


FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        cache = "no-cache" if not full_path.startswith("assets/") else "public, max-age=31536000, immutable"
        return FileResponse(file_path, headers={"Cache-Control": cache})
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
