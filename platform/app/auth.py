import os
import secrets
import sqlite3
import string
import time
from typing import Optional

import jwt
from fastapi import Request, Response
from passlib.context import CryptContext

from .db import db

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
SESSION_HOURS = 6
COOKIE_NAME = "ctf_session"

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password, password_hash)
    except ValueError:
        return False


def create_user(username: str) -> Optional[tuple[int, str]]:
    """Create a user. Returns (user_id, plaintext_password) or None if name taken."""
    password = generate_password()
    pw_hash = hash_password(password)
    try:
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, pw_hash),
            )
            return cur.lastrowid, password
    except sqlite3.IntegrityError:
        return None


def authenticate(username: str, password: str) -> Optional[int]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return row["id"]


def issue_session(user_id: int, username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + SESSION_HOURS * 3600,
    }
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        samesite="strict",
    )


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return {"id": int(payload["sub"]), "username": payload["username"]}
