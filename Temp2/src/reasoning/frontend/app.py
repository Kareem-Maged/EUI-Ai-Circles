import asyncio
import json
import queue
import threading
import time
from datetime import datetime

import requests
import streamlit as st
import websockets
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="Student Group Chat",
    page_icon="💬",
    layout="wide",
)

st.markdown("""
<style>
.msg { padding: 9px 12px; margin: 7px 0; border-radius: 12px; background: #f1f3f5; }
.mine { background: #dbeafe; margin-left: 20%; }
.ai-msg { background: #f3e8ff; border-left: 3px solid #a855f7; }
.meta { font-size: 0.75rem; color: #777; }
.system { text-align: center; color: #888; font-size: 0.8rem; margin: 8px; }
</style>
""", unsafe_allow_html=True)

DEFAULT_BACKEND = "http://localhost:8000"
AI_DISPLAY_NAME = "AI Facilitator 🤖"  # must match backend's AI_DISPLAY_NAME

defaults = {
    "backend_url": DEFAULT_BACKEND,
    "token": None,
    "username": "",
    "display_name": "",
    "group_code": "",
    "group_name": "",
    "messages": [],
    "users": [],
    "connected": False,
    "show_profile": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if "incoming_q" not in st.session_state:
    st.session_state.incoming_q = queue.Queue()
if "outgoing_q" not in st.session_state:
    st.session_state.outgoing_q = queue.Queue()
if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


# ---------------- websocket plumbing (unchanged pattern: thread only
# touches queues, main thread is the only one touching session_state) ----

def websocket_worker(ws_url, incoming_q, outgoing_q, stop_event):
    async def run():
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                incoming_q.put({"type": "_connected"})

                while not stop_event.is_set():
                    try:
                        while True:
                            item = outgoing_q.get_nowait()
                            await ws.send(json.dumps(item))
                    except queue.Empty:
                        pass

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.25)
                        incoming_q.put(json.loads(raw))
                    except asyncio.TimeoutError:
                        pass

                # One last flush: a 'leave' message queued right before
                # stop_event was set must still go out, or the server
                # will treat this as a silent disconnect instead of an
                # explicit leave.
                try:
                    while True:
                        item = outgoing_q.get_nowait()
                        await ws.send(json.dumps(item))
                except queue.Empty:
                    pass

                await ws.close()
                incoming_q.put({"type": "system", "message": "Disconnected."})

        except Exception as e:
            incoming_q.put({"type": "system", "message": f"Connection closed: {e}"})
        finally:
            incoming_q.put({"type": "_closed"})

    asyncio.run(run())


def drain_incoming():
    q = st.session_state.incoming_q
    while True:
        try:
            data = q.get_nowait()
        except queue.Empty:
            break

        if data["type"] == "_connected":
            st.session_state.connected = True
        elif data["type"] == "_closed":
            st.session_state.connected = False
        elif data["type"] in ("message", "system"):
            st.session_state.messages.append(data)
            st.session_state.messages = st.session_state.messages[-200:]
        elif data["type"] == "users":
            st.session_state.users = data["users"]


def wait_for_connection(timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = st.session_state.incoming_q.get(timeout=0.1)
        except queue.Empty:
            continue
        if data["type"] == "_connected":
            st.session_state.connected = True
            return True
        elif data["type"] in ("_closed", "system"):
            st.session_state.messages.append(data)
            return False
    return False


def start_connection():
    group = st.session_state.group_code.strip().upper()
    ws_http = st.session_state.backend_url.rstrip("/")
    ws_base = ws_http.replace("https://", "wss://").replace("http://", "ws://")
    # Token travels as a query param -- browsers/websocket clients can't
    # reliably set custom headers on the handshake. Use wss:// in
    # production so this isn't sent in the clear.
    ws_url = f"{ws_base}/ws/{group}?token={st.session_state.token}"

    st.session_state.messages = []
    st.session_state.users = []
    st.session_state.incoming_q = queue.Queue()
    st.session_state.outgoing_q = queue.Queue()
    st.session_state.stop_event = threading.Event()

    try:
        response = requests.get(
            f"{ws_http}/groups/{group}/messages",
            headers=auth_headers(),
            timeout=5,
        )
        if response.ok:
            st.session_state.messages = response.json()
    except Exception:
        pass

    thread = threading.Thread(
        target=websocket_worker,
        args=(ws_url, st.session_state.incoming_q, st.session_state.outgoing_q, st.session_state.stop_event),
        daemon=True,
    )
    thread.start()
    st.session_state.ws_thread = thread


def stop_connection():
    # Tell the server this is a deliberate leave, not a dropped connection
    # -- the backend only announces "X left the group" for this signal.
    try:
        st.session_state.outgoing_q.put({"type": "leave"})
    except Exception:
        pass

    # Give the background thread a moment to actually send it before we
    # signal shutdown -- otherwise stop_event can win the race and the
    # loop exits without flushing the queue in time.
    time.sleep(0.3)

    st.session_state.stop_event.set()
    thread = st.session_state.get("ws_thread")
    if thread is not None:
        thread.join(timeout=2)
    st.session_state.connected = False
    st.session_state.messages = []
    st.session_state.users = []


def logout():
    if st.session_state.connected:
        stop_connection()
    for key, value in defaults.items():
        st.session_state[key] = value


st.title("💬 Student Group Chat")
drain_incoming()

# ==================== 1. LOGIN / REGISTER ====================
if not st.session_state.token:
    st.subheader("Sign in")

    tab_login, tab_register = st.tabs(["Log in", "Create account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            backend_url = st.text_input("Backend URL", value=st.session_state.backend_url, key="login_backend")
            submitted = st.form_submit_button("Log in", use_container_width=True)

        if submitted:
            st.session_state.backend_url = backend_url
            try:
                resp = requests.post(
                    f"{backend_url.rstrip('/')}/auth/login",
                    json={"username": username, "password": password},
                    timeout=5,
                )
                if resp.ok:
                    data = resp.json()
                    st.session_state.token = data["token"]
                    st.session_state.username = data["username"]
                    st.session_state.display_name = data["display_name"]
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Login failed."))
            except Exception as e:
                st.error(f"Cannot reach backend: {e}")

    with tab_register:
        with st.form("register_form"):
            r_display = st.text_input("Your name", key="reg_display")
            r_username = st.text_input("Choose a username", key="reg_username")
            r_password = st.text_input("Choose a password", type="password", key="reg_password")
            r_backend = st.text_input("Backend URL", value=st.session_state.backend_url, key="reg_backend")
            r_submitted = st.form_submit_button("Create account", use_container_width=True)

        if r_submitted:
            st.session_state.backend_url = r_backend
            try:
                resp = requests.post(
                    f"{r_backend.rstrip('/')}/auth/register",
                    json={"username": r_username, "password": r_password, "display_name": r_display},
                    timeout=5,
                )
                if resp.ok:
                    data = resp.json()
                    st.session_state.token = data["token"]
                    st.session_state.username = data["username"]
                    st.session_state.display_name = data["display_name"]
                    st.success("Account created!")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Registration failed."))
            except Exception as e:
                st.error(f"Cannot reach backend: {e}")

    st.stop()

# ==================== 2. JOIN / CREATE A GROUP ====================
if not st.session_state.connected:
    top_l, top_mid, top_r = st.columns([4, 1, 1])
    with top_l:
        st.caption(f"Signed in as **{st.session_state.display_name}** (@{st.session_state.username})")
    with top_mid:
        if st.button("👤 Profile", use_container_width=True):
            st.session_state.show_profile = not st.session_state.show_profile
            st.rerun()
    with top_r:
        if st.button("Log out", use_container_width=True):
            logout()
            st.rerun()

    if st.session_state.show_profile:
        st.divider()
        st.subheader("👤 My Profile")

        try:
            resp = requests.get(
                f"{st.session_state.backend_url.rstrip('/')}/me/profile",
                headers=auth_headers(),
                timeout=5,
            )
        except Exception as e:
            resp = None
            st.error(f"Cannot reach backend: {e}")

        if resp is not None:
            if resp.ok:
                profile = resp.json()

                c1, c2, c3 = st.columns(3)
                c1.metric("Display name", profile["display_name"])
                c2.metric("Username", f"@{profile['username']}")
                c3.metric("Total messages sent", profile["total_messages"])

                try:
                    joined_dt = datetime.fromisoformat(profile["member_since"].replace("Z", "+00:00"))
                    st.caption(f"Member since {joined_dt.strftime('%B %d, %Y')}")
                except Exception:
                    pass

                st.markdown("#### Your groups")
                if not profile["groups"]:
                    st.info("You haven't joined any groups yet.")
                else:
                    for g in profile["groups"]:
                        with st.container(border=True):
                            log_key = f"log_{g['code']}"
                            logs_loaded = log_key in st.session_state

                            gc1, gc2, gc3 = st.columns([3, 1, 1])
                            gc1.markdown(f"**{g['name']}**  ·  `{g['code']}`")

                            if logs_loaded:
                                # Trust the actually-loaded data over the
                                # separately-fetched summary count, which
                                # can be a moment stale.
                                gc2.write(f"💬 {len(st.session_state[log_key])} messages")
                            else:
                                gc2.write(f"💬 {g['message_count']} messages (approx.)")

                            last = g.get("last_message_at")
                            if last:
                                try:
                                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                                    gc3.write(f"Last: {last_dt.strftime('%b %d, %H:%M')}")
                                except Exception:
                                    gc3.write("")
                            else:
                                gc3.write("No messages yet")

                            if st.button("📜 Load my messages", key=f"load_{g['code']}"):
                                try:
                                    log_resp = requests.get(
                                        f"{st.session_state.backend_url.rstrip('/')}/groups/{g['code']}/my-messages",
                                        headers=auth_headers(),
                                        params={"limit": 500},
                                        timeout=5,
                                    )
                                    st.session_state[log_key] = log_resp.json() if log_resp.ok else []
                                except Exception as e:
                                    st.session_state[log_key] = []
                                    st.error(f"Could not load log: {e}")

                            if log_key in st.session_state:
                                logs = st.session_state[log_key]
                                if not logs:
                                    st.caption("You haven't sent any messages in this group yet.")
                                else:
                                    with st.container(height=250):
                                        for m in logs:
                                            try:
                                                dt = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))
                                                ts = dt.strftime("%Y-%m-%d %H:%M")
                                            except Exception:
                                                ts = m.get("created_at", "")
                                            st.markdown(f"`{ts}` {m['message']}")

                                    log_text = "\n".join(
                                        f"[{m.get('created_at', '')}] {m['message']}"
                                        for m in logs
                                    )
                                    st.download_button(
                                        label="⬇️ Download my messages (.txt)",
                                        data=log_text,
                                        file_name=f"{g['code']}_{g['name'].replace(' ', '_')}_my_messages.txt",
                                        mime="text/plain",
                                        key=f"dl_{g['code']}",
                                        use_container_width=True,
                                    )
            else:
                st.error(resp.json().get("detail", "Could not load profile."))

        st.divider()
        st.stop()

    # Groups this account has joined before -- pulled from the backend,
    # so students don't need to remember/re-type codes each session.
    try:
        my_groups_resp = requests.get(
            f"{st.session_state.backend_url.rstrip('/')}/me/groups",
            headers=auth_headers(),
            timeout=5,
        )
        my_groups = my_groups_resp.json() if my_groups_resp.ok else []
    except Exception:
        my_groups = []

    if my_groups:
        st.subheader("Your groups")
        for g in my_groups:
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{g['name']}**  ·  `{g['code']}`")
            if c2.button("Open", key=f"open_{g['code']}", use_container_width=True):
                st.session_state.group_code = g["code"]
                st.session_state.group_name = g["name"]
                start_connection()
                with st.spinner("Connecting..."):
                    ok = wait_for_connection(timeout=5.0)
                if ok:
                    st.rerun()
                else:
                    st.error("Could not connect to the chat server.")
        st.divider()

    st.subheader("Join a group by code")
    with st.form("join_form"):
        group_code = st.text_input("Group code", max_chars=6).upper()
        submitted = st.form_submit_button("Join group", use_container_width=True)

        if submitted:
            if not group_code.strip():
                st.error("Enter the group code.")
            else:
                try:
                    resp = requests.get(
                        f"{st.session_state.backend_url.rstrip('/')}/groups/{group_code}",
                        timeout=5,
                    )
                    if not resp.ok or not resp.json().get("exists"):
                        st.error("Group not found.")
                    else:
                        st.session_state.group_code = group_code
                        st.session_state.group_name = resp.json()["name"]
                        start_connection()
                        with st.spinner("Connecting to chat..."):
                            ok = wait_for_connection(timeout=5.0)
                        if ok:
                            st.rerun()
                        else:
                            st.error("Could not connect to the chat server.")
                except Exception as e:
                    st.error(f"Cannot connect to backend: {e}")

    st.divider()

    st.subheader("Create a group")
    group_name = st.text_input("Group name", placeholder="Python Class")
    lesson_concept = st.text_input(
        "Lesson concept (optional)",
        placeholder="e.g. recursion, the water cycle, supply and demand",
        help="If set, the AI facilitator posts one open discussion question about this topic when the group is created.",
    )
    if st.button("Create group"):
        if not group_name.strip():
            st.warning("Enter a group name.")
        else:
            try:
                resp = requests.post(
                    f"{st.session_state.backend_url.rstrip('/')}/groups",
                    json={"name": group_name, "lesson_concept": lesson_concept.strip() or None},
                    headers=auth_headers(),
                    timeout=15,  # generating the opening question can take a moment
                )
                if resp.ok:
                    result = resp.json()
                    st.success(f"Group created! Code: {result['code']}")
                    st.code(result["code"])
                else:
                    st.error(resp.json().get("detail", resp.text))
            except Exception as e:
                st.error(f"Cannot connect to backend: {e}")

# ==================== 3. CHAT SCREEN ====================
else:
    st_autorefresh(interval=800, key="chat_autorefresh")

    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(f"💬 {st.session_state.group_name}")
        st.caption(
            f"Group code: {st.session_state.group_code} · "
            f"Signed in as {st.session_state.display_name} · "
            f"{'🟢 Connected' if st.session_state.connected else '🔴 Disconnected'}"
        )
    with col2:
        if st.button("Leave group", use_container_width=True):
            stop_connection()
            st.rerun()

    left, right = st.columns([4, 1])

    with left:
        for item in st.session_state.messages:
            if item.get("type") == "system":
                st.markdown(f'<div class="system">{item["message"]}</div>', unsafe_allow_html=True)
                continue

            username = item.get("username", "")
            message = item.get("message", "")
            created = item.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                time_text = dt.strftime("%H:%M")
            except Exception:
                time_text = ""

            if username == AI_DISPLAY_NAME:
                css = "msg ai-msg"
            elif username == st.session_state.username:
                css = "msg mine"
            else:
                css = "msg"

            st.markdown(
                f'<div class="{css}"><b>{username}</b><div>{message}</div>'
                f'<div class="meta">{time_text}</div></div>',
                unsafe_allow_html=True,
            )

        st.divider()
        with st.form("message_form", clear_on_submit=True):
            message = st.text_input(
                "Message",
                placeholder="Write a message... (mention @AI to ask the facilitator)",
                label_visibility="collapsed",
            )
            send = st.form_submit_button("Send", use_container_width=True)
            if send and message.strip():
                st.session_state.outgoing_q.put({"type": "message", "message": message.strip()})
                st.rerun()

    with right:
        st.markdown("### 👥 Online")
        st.metric("Students", len(st.session_state.users))
        for user in st.session_state.users:
            st.write(f"🟢 {user}")