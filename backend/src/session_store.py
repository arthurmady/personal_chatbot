import json
import time
from pathlib import Path
from threading import Lock

SESSIONS_FILE = Path("data/sessions.json")
_lock = Lock()


def _now() -> float:
    return time.time()


def load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    return {}


def _save(sessions: dict):
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def create_session(session_id: str):
    with _lock:
        sessions = load_sessions()
        sessions[session_id] = {
            "created_at": _now(),
            "messages": [],
            "summary": "",
        }
        _save(sessions)


def append_message(session_id: str, role: str, content: str, response_meta: dict | None = None):
    with _lock:
        sessions = load_sessions()
        if session_id not in sessions:
            sessions[session_id] = {"created_at": _now(), "messages": [], "summary": ""}
        entry = {"role": role, "content": content, "timestamp": _now()}
        if response_meta:
            entry["meta"] = response_meta
        sessions[session_id]["messages"].append(entry)
        _save(sessions)


def update_summary(session_id: str, summary: str):
    with _lock:
        sessions = load_sessions()
        if session_id in sessions:
            sessions[session_id]["summary"] = summary
            _save(sessions)


def delete_session(session_id: str) -> bool:
    with _lock:
        sessions = load_sessions()
        if session_id in sessions:
            del sessions[session_id]
            _save(sessions)
            return True
        return False


def get_session(session_id: str) -> dict | None:
    return load_sessions().get(session_id)


def list_sessions() -> list[dict]:
    sessions = load_sessions()
    result = []
    for sid, data in sessions.items():
        msg_count = len(data.get("messages", []))
        result.append({
            "session_id": sid,
            "created_at": data.get("created_at", 0),
            "message_count": msg_count,
            "summary": data.get("summary", ""),
        })
    result.sort(key=lambda s: s["created_at"], reverse=True)
    return result


def get_stats() -> dict:
    sessions = load_sessions()
    total_sessions = len(sessions)
    total_messages = sum(len(s.get("messages", [])) for s in sessions.values())
    total_user_msgs = sum(
        1 for s in sessions.values()
        for m in s.get("messages", [])
        if m.get("role") == "user"
    )
    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_user_queries": total_user_msgs,
    }
