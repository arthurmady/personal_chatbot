import uuid
import sys
from pathlib import Path
from fastapi import Header, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ADMIN_PASSWORD

_tokens: dict[str, float] = {}


def login(password: str) -> str | None:
    if password != ADMIN_PASSWORD:
        return None
    import time
    token = str(uuid.uuid4())
    _tokens[token] = time.time()
    return token


def verify_token(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    if token not in _tokens:
        raise HTTPException(status_code=401, detail="invalid token")
    return token
