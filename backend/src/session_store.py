import json
import os
import tempfile
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
    fd, tmp_path = tempfile.mkstemp(dir=SESSIONS_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SESSIONS_FILE)
    except BaseException:
        os.unlink(tmp_path)
        raise


def _empty_session(user_agent: str = "") -> dict:
    return {
        "created_at": _now(),
        "messages": [],
        "summaries": [],
        "essentials_done": [],
        "details_done": [],
        "user_agent": user_agent,
    }


def create_session(session_id: str, user_agent: str = ""):
    with _lock:
        sessions = load_sessions()
        sessions[session_id] = _empty_session(user_agent)
        _save(sessions)


def append_message(session_id: str, role: str, content: str, response_meta: dict | None = None):
    with _lock:
        sessions = load_sessions()
        if session_id not in sessions:
            sessions[session_id] = _empty_session()
        entry = {"role": role, "content": content, "timestamp": _now()}
        if response_meta:
            entry["meta"] = response_meta
        sessions[session_id]["messages"].append(entry)
        _save(sessions)


def record_response(session_id: str, content: str, response_meta: dict | None,
                    turn_summary: str, essentials_done: list[str], details_done: list[str],
                    summary_ids: list[str] | None = None):
    with _lock:
        sessions = load_sessions()
        session = sessions.setdefault(session_id, _empty_session())
        entry = {"role": "bot", "content": content, "timestamp": _now()}
        if response_meta:
            entry["meta"] = response_meta
        session["messages"].append(entry)
        if turn_summary:
            session.setdefault("summaries", []).append(turn_summary)
        session["essentials_done"] = essentials_done
        session["details_done"] = details_done
        if summary_ids is not None:
            session["summary_ids"] = summary_ids
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
            "summaries": data.get("summaries", []),
            "user_agent": data.get("user_agent", ""),
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
