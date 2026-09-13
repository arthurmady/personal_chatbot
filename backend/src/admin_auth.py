import hmac
import os
import time
import uuid
import sys
from pathlib import Path
from fastapi import Cookie, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ADMIN_PASSWORD

_tokens: dict[str, float] = {}
TOKEN_TTL = int(os.getenv("ADMIN_TOKEN_TTL", "1800"))


def login(password: str) -> str | None:
    if not ADMIN_PASSWORD:
        return None
    if not hmac.compare_digest(password, ADMIN_PASSWORD):
        return None
    token = str(uuid.uuid4())
    _tokens[token] = time.time()
    return token


def verify_token(admin_token: str = Cookie(None)) -> str:
    if not admin_token:
        raise HTTPException(status_code=401, detail="missing token")
    if admin_token not in _tokens:
        raise HTTPException(status_code=401, detail="invalid token")
    if time.time() - _tokens[admin_token] > TOKEN_TTL:
        del _tokens[admin_token]
        raise HTTPException(status_code=401, detail="token expired")
    return admin_token


def revoke_token(token: str):
    _tokens.pop(token, None)
