"""
Student Group Chat API with accounts.

pip install fastapi uvicorn websockets bcrypt pyjwt

Run:  uvicorn backend_main_auth:app --host 0.0.0.0 --port 8000
"""

import asyncio
import secrets
import sqlite3
import string
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .Text_Generation import tutor_reply
from .Contribution_Tracking import tracker

DB = "chat.db"

# ---- Sawa-Ed tutor bot ----
SAWA_ED_MENTION = "@sawa-edu"
SAWA_ED_USERNAME = "Sawa-Edu"

# Stage 1 (warm-up) has no RAG/lesson content wired up yet, so we hardcode
# an empty context for now. Once retrieval is built, this should be
# replaced with the retrieved lesson chunk for whatever stage/topic the
# group is currently in.

# STAGE1_CONTEXT = ("Force is a push or pull that can change an object's state of motion — "
#     "making it start moving, stop, speed up, slow down, or change direction. "
#     "Force is measured in Newtons (N). A simple everyday example: when you "
#     "push a shopping cart, you are applying a force to it; the heavier the "
#     "cart, the more force you need to get it moving at the same rate. "
#     "According to Newton's Second Law, force equals mass times acceleration "
#     "(F = m × a)."
# )

# In production, set this via an environment variable -- never hardcode
# a real secret in source control.
JWT_SECRET = "student-chat-secret-2026"
JWT_ALG = "HS256"
JWT_EXPIRE_DAYS = 7

app = FastAPI(title="Student Group Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# group_code -> {user_id: (websocket, username)}
# Keyed by user_id (not by websocket) so we can detect "this user already
# has a connection in this group" and evict the stale one instead of
# ending up with duplicate entries in the online list.
connections: Dict[str, Dict[int, tuple]] = defaultdict(dict)


def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_code TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            joined_at TEXT NOT NULL,
            UNIQUE(group_code, user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_code TEXT NOT NULL,
            user_id INTEGER REFERENCES users(id),
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # Kept separate from `messages` on purpose: contribution tiers are a
    # derived scoring signal, not part of raw chat history, and this
    # table is populated asynchronously (after the message is already
    # sent/broadcast) rather than in the same transaction as the insert
    # above -- see track_contribution().
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL REFERENCES messages(id),
            group_code TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            username TEXT NOT NULL,
            tier TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ---------- auth helpers ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),  # PyJWT requires 'sub' to be a string
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(authorization: str = Header(None)) -> dict:
    """FastAPI dependency: requires 'Authorization: Bearer <token>' header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    return {"id": int(payload["sub"]), "username": payload["username"]}


def get_user_from_ws_token(token: Optional[str]) -> Optional[dict]:
    """Same as get_current_user but for a raw token string (used by the websocket)."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        return {"id": int(payload["sub"]), "username": payload["username"]}
    except HTTPException:
        return None


# ---------- schemas ----------

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateGroup(BaseModel):
    name: str


def generate_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


# ---------- auth endpoints ----------

@app.post("/auth/register")
def register(data: RegisterRequest):
    username = data.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="Username already taken")

    password_hash = hash_password(data.password)
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, data.display_name.strip(), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    token = create_token(user_id, username)
    return {"token": token, "username": username, "display_name": data.display_name.strip()}


@app.post("/auth/login")
def login(data: LoginRequest):
    username = data.username.strip().lower()

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_token(user["id"], user["username"])
    return {"token": token, "username": user["username"], "display_name": user["display_name"]}


@app.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    conn = get_db()
    user = conn.execute("SELECT username, display_name, created_at FROM users WHERE id = ?", (current_user["id"],)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)


@app.get("/me/profile")
def my_profile(current_user: dict = Depends(get_current_user)):
    """
    Full profile: account info + per-group stats (message count, last
    activity), proving messages really are saved per student per group.
    """
    conn = get_db()

    user = conn.execute(
        "SELECT username, display_name, created_at FROM users WHERE id = ?",
        (current_user["id"],),
    ).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    groups = conn.execute(
        """
        SELECT
            g.code,
            g.name,
            gm.joined_at,
            (SELECT COUNT(*) FROM messages m
             WHERE m.group_code = g.code AND m.user_id = ?) AS message_count,
            (SELECT MAX(created_at) FROM messages m
             WHERE m.group_code = g.code AND m.user_id = ?) AS last_message_at
        FROM group_members gm
        JOIN groups g ON g.code = gm.group_code
        WHERE gm.user_id = ?
        ORDER BY gm.joined_at DESC
        """,
        (current_user["id"], current_user["id"], current_user["id"]),
    ).fetchall()

    total_messages = conn.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE user_id = ?",
        (current_user["id"],),
    ).fetchone()["c"]

    conn.close()

    return {
        "username": user["username"],
        "display_name": user["display_name"],
        "member_since": user["created_at"],
        "total_messages": total_messages,
        "groups": [dict(g) for g in groups],
    }


@app.get("/me/groups")
def my_groups(current_user: dict = Depends(get_current_user)):
    """Groups this student has previously joined -- persisted per account."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT g.code, g.name, gm.joined_at
        FROM group_members gm
        JOIN groups g ON g.code = gm.group_code
        WHERE gm.user_id = ?
        ORDER BY gm.joined_at DESC
        """,
        (current_user["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- group endpoints (require login) ----------

@app.get("/")
def root():
    return {"status": "ok", "service": "Student Group Chat"}


@app.post("/groups")
def create_group(data: CreateGroup, current_user: dict = Depends(get_current_user)):
    conn = get_db()

    while True:
        code = generate_code()
        try:
            conn.execute(
                "INSERT INTO groups (name, code, created_by, created_at) VALUES (?, ?, ?, ?)",
                (data.name.strip(), code, current_user["id"], datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(
                "INSERT INTO group_members (group_code, user_id, joined_at) VALUES (?, ?, ?)",
                (code, current_user["id"], datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
            return {"name": data.name.strip(), "code": code}
        except sqlite3.IntegrityError:
            continue


@app.get("/groups/{code}")
def get_group(code: str):
    conn = get_db()
    group = conn.execute(
        "SELECT name, code, created_at FROM groups WHERE code = ?",
        (code.upper(),),
    ).fetchone()
    conn.close()

    if not group:
        return {"exists": False}
    return {"exists": True, **dict(group)}


@app.get("/groups/{code}/messages")
def get_messages(code: str, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """All messages in the group, from every student -- used for chat history on join."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT username, message, created_at
        FROM messages
        WHERE group_code = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (code.upper(), min(limit, 500)),
    ).fetchall()
    conn.close()
    return list(reversed([dict(row) for row in rows]))


@app.get("/groups/{code}/my-messages")
def get_my_messages(code: str, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Only the logged-in student's own messages in this group -- used by the profile log."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT username, message, created_at
        FROM messages
        WHERE group_code = ? AND user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (code.upper(), current_user["id"], min(limit, 500)),
    ).fetchall()
    conn.close()
    return list(reversed([dict(row) for row in rows]))


# ---------- websocket ----------

async def broadcast(group_code: str, payload: dict):
    dead = []
    for uid, (ws, _uname) in list(connections[group_code].items()):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(uid)
    for uid in dead:
        connections[group_code].pop(uid, None)


async def broadcast_users(group_code: str):
    users = [uname for (_ws, uname) in connections[group_code].values()]
    await broadcast(group_code, {"type": "users", "users": users, "count": len(users)})


async def handle_sawa_ed_mention(group_code: str, instruction: str):
    """
    Runs the tutor model and broadcasts its reply. `tutor_reply` is a
    synchronous, blocking call (classifier + model.generate), so it's
    pushed onto a worker thread with asyncio.to_thread. That keeps the
    event loop free to keep serving every other student/group while the
    model is running, instead of freezing all chat for however long
    generation takes.
    """
    result = await asyncio.to_thread(tutor_reply, instruction)
    reply = result["response"]
    timestamp = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    conn.execute(
        """
        INSERT INTO messages (group_code, user_id, username, message, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (group_code, None, SAWA_ED_USERNAME, reply, timestamp),
    )
    conn.commit()
    conn.close()

    await broadcast(
        group_code,
        {
            "type": "message",
            "username": SAWA_ED_USERNAME,
            "message": reply,
            "created_at": timestamp,
        },
    )


async def track_contribution(group_code: str, user_id: int, username: str, message_id: int, message: str):
    """
    Classifies a student's message into a contribution tier and logs it.
    Fired with asyncio.create_task() rather than awaited inline in the
    websocket loop, so the sender's message is broadcast immediately and
    nobody waits on this classification call -- it just backfills the
    contributions table a moment later. Runs the classifier itself in a
    worker thread (asyncio.to_thread) since `tracker` is a blocking model
    call, same reasoning as handle_sawa_ed_mention.
    """
    result = await asyncio.to_thread(tracker, message)
    timestamp = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    conn.execute(
        """
        INSERT INTO contributions (message_id, group_code, user_id, username, tier, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, group_code, user_id, username, result["tier"], result["confidence"], timestamp),
    )
    conn.commit()
    conn.close()


@app.websocket("/ws/{group_code}")
async def websocket_endpoint(websocket: WebSocket, group_code: str, token: str):
    """
    Token is passed as a query param since browsers/clients can't always
    set custom headers on a WebSocket handshake reliably. Use wss:// in
    production so the token isn't sent in the clear.
    """
    group_code = group_code.upper().strip()

    user = get_user_from_ws_token(token)
    if not user:
        await websocket.close(code=1008)  # policy violation
        return

    conn = get_db()
    group = conn.execute("SELECT code FROM groups WHERE code = ?", (group_code,)).fetchone()
    if not group:
        conn.close()
        await websocket.close(code=1008)
        return

    # Persist / update membership -- this is what makes "their groups"
    # show up in /me/groups on future logins.
    conn.execute(
        "INSERT OR IGNORE INTO group_members (group_code, user_id, joined_at) VALUES (?, ?, ?)",
        (group_code, user["id"], datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    await websocket.accept()

    # If this user already has a live connection in this group (stale tab,
    # page refresh that orphaned the old thread, etc.), close it out first
    # so the online list never shows the same student twice.
    existing = connections[group_code].get(user["id"])
    if existing is not None:
        old_ws, _old_uname = existing
        try:
            await old_ws.close(code=1000)
        except Exception:
            pass

    connections[group_code][user["id"]] = (websocket, user["username"])

    await broadcast(group_code, {"type": "system", "message": f"{user['username']} joined the group."})
    await broadcast_users(group_code)

    explicit_leave = False

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "leave":
                # Student explicitly clicked "Leave group" -- stop the loop
                # so we fall into the finally block and announce it below.
                explicit_leave = True
                break

            if msg_type != "message":
                continue

            message = str(data.get("message", "")).strip()[:2000]
            if not message:
                continue

            timestamp = datetime.now(timezone.utc).isoformat()

            conn = get_db()
            cursor = conn.execute(
                """
                INSERT INTO messages (group_code, user_id, username, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_code, user["id"], user["username"], message, timestamp),
            )
            message_id = cursor.lastrowid
            conn.commit()
            conn.close()

            await broadcast(
                group_code,
                {
                    "type": "message",
                    "username": user["username"],
                    "message": message,
                    "created_at": timestamp,
                },
            )

            # Contribution tracking covers the whole session, on every
            # message. Fire-and-forget: the sender shouldn't wait on the
            # classifier, so this is a background task, not an await.
            asyncio.create_task(
                track_contribution(group_code, user["id"], user["username"], message_id, message)
            )

            # Stage 1 (warm-up): AI stays silent and lets students talk
            # freely, unless a student explicitly calls on it.
            if SAWA_ED_MENTION in message.lower():
                await handle_sawa_ed_mention(group_code, message)

    except WebSocketDisconnect:
        pass
    finally:
        current = connections[group_code].get(user["id"])
        was_active = current is not None and current[0] is websocket

        if was_active:
            connections[group_code].pop(user["id"], None)

            if explicit_leave:
                # Deliberate "Leave group" click -- announce it.
                if connections[group_code]:
                    await broadcast(group_code, {"type": "system", "message": f"{user['username']} left the group."})
            # else: tab closed / connection dropped silently -- just
            # update the online count below, no "left the group" text.

            await broadcast_users(group_code)

        if not connections[group_code]:
            connections.pop(group_code, None)

##########################