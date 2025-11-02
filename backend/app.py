import os
import time
import datetime as dt
from functools import wraps
from typing import List, Dict, Any, Tuple, Optional

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, jsonify, request
from flask_cors import CORS
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
import redis


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/todo_app",
)
JWT_SECRET = os.getenv("JWT_SECRET", "dev_super_secret_change_me")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _parse_bearer(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def require_auth(fn):  # type: ignore[no-redef]
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _parse_bearer(request.headers.get("Authorization"))
        if not token:
            return jsonify({"error": "missing bearer token"}), 401
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if data.get("type") != "access":
                return jsonify({"error": "invalid token type"}), 401
            user_id = int(data.get("sub"))
        except Exception as e:
            return jsonify({"error": f"invalid token: {e}"}), 401
        return fn(user_id=user_id, *args, **kwargs)
    return wrapper


def _issue_tokens(user_id: int) -> Tuple[str, str, str]:
    now = dt.datetime.utcnow()
    access_payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
    }
    access = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")

    jti = f"{user_id}:{int(now.timestamp())}"
    refresh_payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(days=REFRESH_TOKEN_DAYS)).timestamp()),
    }
    refresh = jwt.encode(refresh_payload, JWT_SECRET, algorithm="HS256")
    return access, refresh, jti


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    minconn = int(os.getenv("PG_MIN_CONN", "1"))
    maxconn = int(os.getenv("PG_MAX_CONN", "10"))
    app.pool = _create_pool_with_retry(DATABASE_URL, minconn, maxconn)  # type: ignore[attr-defined]
    try:
        app.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)  # type: ignore[attr-defined]
        app.redis.ping()  # Test connection
        print(f"Redis connected: {REDIS_URL}")
    except Exception as e:
        print(f"Redis connection failed: {e}, continuing without Redis")
        app.redis = None  # type: ignore[attr-defined]

    with app.app_context():
        _ensure_schema(app.pool)  # type: ignore[attr-defined]

    @app.get("/")
    def index() -> Any:
        return (
            """
            <html>
              <head><title>Flask Backend</title></head>
              <body style="font-family: sans-serif; padding: 16px;">
                <h1>Flask backend is running</h1>
                <ul>
                  <li><a href="/api/health">/api/health</a> — health check</li>
                  <li><a href="/api/todos">/api/todos</a> — list todos (JSON)</li>
                  <li><a href="/debug/db">/debug/db</a> — DB status</li>
                </ul>
                <p>Frontend: <a href="http://localhost:3001/todos">http://localhost:3001/todos</a></p>
                <p>Adminer (DB UI): <a href="http://localhost:8080">http://localhost:8080</a></p>
              </body>
            </html>
            """
        )

    @app.get("/api/health")
    def health() -> Any:
        return {"ok": True}

    # ---------- AUTH ----------
    @app.post("/api/signup")
    def signup() -> Any:
        print("Signup request received")
        payload = request.get_json(force=True) or {}
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        print(f"Signup attempt for email: {email}")
        if not email or not password:
            return jsonify({"error": "email and password required"}), 400

        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cur.fetchone():
                        return jsonify({"error": "email already registered"}), 409
                    pwd = generate_password_hash(password)
                    cur.execute(
                        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                        (email, pwd),
                    )
                    user_id = cur.fetchone()[0]
            access, refresh, jti = _issue_tokens(user_id)
            if app.redis:  # type: ignore[attr-defined]
                try:
                    app.redis.setex(f"refresh:{jti}", REFRESH_TOKEN_DAYS * 24 * 3600, str(user_id))  # type: ignore[attr-defined]
                except Exception as e:
                    print(f"Redis setex failed: {e}")
            return jsonify({"accessToken": access, "refreshToken": refresh})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/login")
    def login() -> Any:
        print("Login request received")
        payload = request.get_json(force=True) or {}
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        print(f"Login attempt for email: {email}")
        if not email or not password:
            return jsonify({"error": "email and password required"}), 400
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, password_hash FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                if not row or not check_password_hash(row[1], password):
                    return jsonify({"error": "invalid credentials"}), 401
                user_id = row[0]
            access, refresh, jti = _issue_tokens(user_id)
            try:
                app.redis.setex(f"refresh:{jti}", REFRESH_TOKEN_DAYS * 24 * 3600, str(user_id))  # type: ignore[attr-defined]
            except Exception:
                pass
            return jsonify({"accessToken": access, "refreshToken": refresh})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/refresh")
    def refresh() -> Any:
        payload = request.get_json(force=True) or {}
        token = payload.get("refreshToken")
        if not token:
            return jsonify({"error": "refreshToken required"}), 400
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if data.get("type") != "refresh":
                return jsonify({"error": "invalid token type"}), 401
            jti = data.get("jti")
            try:
                uid = app.redis.get(f"refresh:{jti}")  # type: ignore[attr-defined]
            except Exception:
                # If Redis is down, treat as invalid refresh
                uid = None
            if uid is None:
                return jsonify({"error": "refresh expired or revoked"}), 401
            user_id = int(uid)
        except Exception as e:
            return jsonify({"error": f"invalid token: {e}"}), 401
        access, refresh_new, jti_new = _issue_tokens(user_id)
        # rotate refresh (optional); here we keep the old too for simplicity
        try:
            app.redis.setex(f"refresh:{jti_new}", REFRESH_TOKEN_DAYS * 24 * 3600, str(user_id))  # type: ignore[attr-defined]
        except Exception:
            pass
        return jsonify({"accessToken": access, "refreshToken": refresh_new})

    @app.get("/api/me")
    @require_auth
    def me(user_id: int) -> Any:  # type: ignore[override]
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, created_at FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                return jsonify({"id": row[0], "email": row[1], "createdAt": row[2].isoformat()})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    # ---------- TODOS (protected) ----------
    @app.get("/api/todos")
    @require_auth
    def list_todos(user_id: int) -> Any:  # type: ignore[override]
        search = request.args.get("search", "").strip()
        status = request.args.get("status", "all")  # all, done, pending
        sort_by = request.args.get("sort", "id")  # id, title, created_at, done
        list_id = request.args.get("list_id")  # filter by list
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                # Build query dynamically
                where_conditions = ["user_id = %s"]
                params = [user_id]
                
                if search:
                    where_conditions.append("title ILIKE %s")
                    params.append(f"%{search}%")
                
                if status == "done":
                    where_conditions.append("done = true")
                elif status == "pending":
                    where_conditions.append("done = false")
                
                if list_id:
                    where_conditions.append("list_id = %s")
                    params.append(int(list_id))
                
                # Sort options
                sort_clause = "ORDER BY"
                if sort_by == "title":
                    sort_clause += " title ASC"
                elif sort_by == "created_at":
                    sort_clause += " id ASC"  # id is our created_at proxy
                elif sort_by == "done":
                    sort_clause += " done ASC, id ASC"
                else:  # default by position, then id
                    sort_clause += " position ASC, id ASC"
                
                query = f"""
                    SELECT id, title, done, created_at, list_id, position 
                    FROM todos 
                    WHERE {' AND '.join(where_conditions)}
                    {sort_clause}
                """
                
                cur.execute(query, params)
                rows = cur.fetchall()
                todos: List[Dict[str, Any]] = [
                    {
                        "id": r[0], 
                        "title": r[1], 
                        "done": r[2],
                        "created_at": r[3].isoformat() if r[3] else None,
                        "list_id": r[4],
                        "position": r[5]
                    } 
                    for r in rows
                ]
                return jsonify(todos)
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/todos")
    @require_auth
    def create_todo(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        list_id = data.get("list_id")
        
        if not title:
            return jsonify({"error": "title is required"}), 400

        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    # If list_id provided, verify it belongs to user
                    if list_id:
                        cur.execute("SELECT id FROM todo_lists WHERE id = %s AND user_id = %s", (list_id, user_id))
                        if not cur.fetchone():
                            return jsonify({"error": "list not found"}), 404
                    
                    cur.execute(
                        "INSERT INTO todos (user_id, list_id, title, done) VALUES (%s, %s, %s, false) RETURNING id, title, done, list_id, position",
                        (user_id, list_id, title),
                    )
                    row = cur.fetchone()
                    return jsonify({
                        "id": row[0], 
                        "title": row[1], 
                        "done": row[2],
                        "list_id": row[3],
                        "position": row[4]
                    }), 201
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.patch("/api/todos/<int:todo_id>")
    @require_auth
    def update_todo(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        title = data.get("title")
        done = data.get("done")

        if title is None and done is None:
            return jsonify({"error": "nothing to update"}), 400

        fields: List[str] = []
        values: List[Any] = []
        if title is not None:
            fields.append("title = %s")
            values.append(str(title))
        if done is not None:
            fields.append("done = %s")
            values.append(bool(done))
        values.extend([user_id, todo_id])

        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE todos SET {', '.join(fields)} WHERE user_id = %s AND id = %s RETURNING id, title, done",
                        tuple(values),
                    )
                    row = cur.fetchone()
                    if not row:
                        return jsonify({"error": "not found"}), 404
                    return jsonify({"id": row[0], "title": row[1], "done": row[2]})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/todos/bulk")
    @require_auth
    def bulk_todos(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        action = data.get("action")  # delete, mark_done, mark_pending
        todo_ids = data.get("todo_ids", [])
        
        if not action or not todo_ids:
            return jsonify({"error": "action and todo_ids required"}), 400
        
        if action not in ["delete", "mark_done", "mark_pending"]:
            return jsonify({"error": "invalid action"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    if action == "delete":
                        cur.execute(
                            "DELETE FROM todos WHERE user_id = %s AND id = ANY(%s) RETURNING id",
                            (user_id, todo_ids)
                        )
                    elif action == "mark_done":
                        cur.execute(
                            "UPDATE todos SET done = true WHERE user_id = %s AND id = ANY(%s) RETURNING id",
                            (user_id, todo_ids)
                        )
                    elif action == "mark_pending":
                        cur.execute(
                            "UPDATE todos SET done = false WHERE user_id = %s AND id = ANY(%s) RETURNING id",
                            (user_id, todo_ids)
                        )
                    
                    affected_ids = [row[0] for row in cur.fetchall()]
                    return jsonify({"affected_count": len(affected_ids), "affected_ids": affected_ids})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/todos/reorder")
    @require_auth
    def reorder_todos(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        todo_positions = data.get("todo_positions", [])  # [{"id": 1, "position": 0}, ...]
        
        if not todo_positions:
            return jsonify({"error": "todo_positions required"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    for item in todo_positions:
                        todo_id = item.get("id")
                        position = item.get("position")
                        if todo_id is None or position is None:
                            continue
                        
                        cur.execute(
                            "UPDATE todos SET position = %s WHERE id = %s AND user_id = %s",
                            (position, todo_id, user_id)
                        )
                    
                    return jsonify({"success": True})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/lists/reorder")
    @require_auth
    def reorder_lists(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        list_positions = data.get("list_positions", [])  # [{"id": 1, "position": 0}, ...]
        
        if not list_positions:
            return jsonify({"error": "list_positions required"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    for item in list_positions:
                        list_id = item.get("id")
                        position = item.get("position")
                        if list_id is None or position is None:
                            continue
                        
                        cur.execute(
                            "UPDATE todo_lists SET position = %s WHERE id = %s AND user_id = %s",
                            (position, list_id, user_id)
                        )
                    
                    return jsonify({"success": True})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/todos/move")
    @require_auth
    def move_todo(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        todo_id = data.get("todo_id")
        new_list_id = data.get("new_list_id")
        new_position = data.get("new_position", 0)
        
        if todo_id is None:
            return jsonify({"error": "todo_id required"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    # Verify todo belongs to user
                    cur.execute("SELECT id FROM todos WHERE id = %s AND user_id = %s", (todo_id, user_id))
                    if not cur.fetchone():
                        return jsonify({"error": "todo not found"}), 404
                    
                    # If new_list_id provided, verify it belongs to user
                    if new_list_id is not None:
                        cur.execute("SELECT id FROM todo_lists WHERE id = %s AND user_id = %s", (new_list_id, user_id))
                        if not cur.fetchone():
                            return jsonify({"error": "list not found"}), 404
                    
                    # Update todo
                    cur.execute(
                        "UPDATE todos SET list_id = %s, position = %s WHERE id = %s AND user_id = %s RETURNING id, title, done, list_id, position",
                        (new_list_id, new_position, todo_id, user_id)
                    )
                    row = cur.fetchone()
                    if not row:
                        return jsonify({"error": "todo not found"}), 404
                    
                    return jsonify({
                        "id": row[0], 
                        "title": row[1], 
                        "done": row[2],
                        "list_id": row[3],
                        "position": row[4]
                    })
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.delete("/api/todos/<int:todo_id>")
    @require_auth
    def delete_todo(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM todos WHERE user_id = %s AND id = %s RETURNING id",
                        (user_id, todo_id),
                    )
                    row = cur.fetchone()
                    if not row:
                        return jsonify({"error": "not found"}), 404
                    return ("", 204)
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    # ---------- LISTS ----------
    @app.get("/api/lists")
    @require_auth
    def get_lists(user_id: int) -> Any:  # type: ignore[override]
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, color, position FROM todo_lists WHERE user_id = %s ORDER BY position ASC",
                    (user_id,)
                )
                rows = cur.fetchall()
                lists = [
                    {"id": r[0], "name": r[1], "color": r[2], "position": r[3]}
                    for r in rows
                ]
                return jsonify(lists)
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/lists")
    @require_auth
    def create_list(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        color = data.get("color", "#3B82F6")
        
        if not name:
            return jsonify({"error": "name is required"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO todo_lists (user_id, name, color) VALUES (%s, %s, %s) RETURNING id, name, color, position",
                        (user_id, name, color)
                    )
                    row = cur.fetchone()
                    return jsonify({"id": row[0], "name": row[1], "color": row[2], "position": row[3]}), 201
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.patch("/api/lists/<int:list_id>")
    @require_auth
    def update_list(list_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        name = data.get("name")
        color = data.get("color")
        position = data.get("position")
        
        if name is None and color is None and position is None:
            return jsonify({"error": "nothing to update"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    fields = []
                    values = []
                    if name is not None:
                        fields.append("name = %s")
                        values.append(str(name))
                    if color is not None:
                        fields.append("color = %s")
                        values.append(str(color))
                    if position is not None:
                        fields.append("position = %s")
                        values.append(int(position))
                    values.extend([user_id, list_id])
                    
                    cur.execute(
                        f"UPDATE todo_lists SET {', '.join(fields)} WHERE user_id = %s AND id = %s RETURNING id, name, color, position",
                        tuple(values)
                    )
                    row = cur.fetchone()
                    if not row:
                        return jsonify({"error": "list not found"}), 404
                    return jsonify({"id": row[0], "name": row[1], "color": row[2], "position": row[3]})
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.delete("/api/lists/<int:list_id>")
    @require_auth
    def delete_list(list_id: int, user_id: int) -> Any:  # type: ignore[override]
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM todo_lists WHERE user_id = %s AND id = %s RETURNING id",
                        (user_id, list_id)
                    )
                    row = cur.fetchone()
                    if not row:
                        return jsonify({"error": "list not found"}), 404
                    return ("", 204)
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    # ---------- SUBTASKS/CHECKLISTS ----------
    @app.get("/api/todos/<int:todo_id>/items")
    @require_auth
    def get_todo_items(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, done, position FROM todo_items WHERE todo_id = %s ORDER BY position ASC",
                    (todo_id,)
                )
                rows = cur.fetchall()
                items = [
                    {"id": r[0], "title": r[1], "done": r[2], "position": r[3]}
                    for r in rows
                ]
                return jsonify(items)
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/todos/<int:todo_id>/items")
    @require_auth
    def create_todo_item(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    # Verify todo belongs to user
                    cur.execute("SELECT id FROM todos WHERE id = %s AND user_id = %s", (todo_id, user_id))
                    if not cur.fetchone():
                        return jsonify({"error": "todo not found"}), 404
                    
                    cur.execute(
                        "INSERT INTO todo_items (todo_id, title) VALUES (%s, %s) RETURNING id, title, done, position",
                        (todo_id, title)
                    )
                    row = cur.fetchone()
                    return jsonify({"id": row[0], "title": row[1], "done": row[2], "position": row[3]}), 201
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    # ---------- COMMENTS ----------
    @app.get("/api/todos/<int:todo_id>/comments")
    @require_auth
    def get_todo_comments(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.content, c.created_at, u.email 
                    FROM todo_comments c 
                    JOIN users u ON c.user_id = u.id 
                    WHERE c.todo_id = %s 
                    ORDER BY c.created_at ASC
                    """,
                    (todo_id,)
                )
                rows = cur.fetchall()
                comments = [
                    {
                        "id": r[0], 
                        "content": r[1], 
                        "created_at": r[2].isoformat(),
                        "author_email": r[3]
                    }
                    for r in rows
                ]
                return jsonify(comments)
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.post("/api/todos/<int:todo_id>/comments")
    @require_auth
    def create_todo_comment(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"error": "content is required"}), 400
        
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn:
                with conn.cursor() as cur:
                    # Verify todo belongs to user
                    cur.execute("SELECT id FROM todos WHERE id = %s AND user_id = %s", (todo_id, user_id))
                    if not cur.fetchone():
                        return jsonify({"error": "todo not found"}), 404
                    
                    cur.execute(
                        "INSERT INTO todo_comments (todo_id, user_id, content) VALUES (%s, %s, %s) RETURNING id, content, created_at",
                        (todo_id, user_id, content)
                    )
                    row = cur.fetchone()
                    return jsonify({
                        "id": row[0], 
                        "content": row[1], 
                        "created_at": row[2].isoformat()
                    }), 201
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    @app.get("/debug/db")
    def debug_db() -> Any:
        conn = app.pool.getconn()  # type: ignore[attr-defined]
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), version();")
                dbname, version = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM todos;")
                count = cur.fetchone()[0]
                return jsonify(
                    {
                        "connected": True,
                        "database": dbname,
                        "server_version": version,
                        "todos_count": count,
                    }
                )
        except Exception as e:
            return jsonify({"connected": False, "error": str(e)}), 500
        finally:
            app.pool.putconn(conn)  # type: ignore[attr-defined]

    return app


def _ensure_schema(pool: SimpleConnectionPool) -> None:
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                # users table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                # lists table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS todo_lists (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        color TEXT DEFAULT '#3B82F6',
                        position INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                
                # todos table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS todos (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        list_id INTEGER REFERENCES todo_lists(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        done BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        parent_id INTEGER REFERENCES todos(id) ON DELETE CASCADE,
                        position INTEGER DEFAULT 0
                    );
                    """
                )
                # ensure columns exist (if table pre-existed)
                cur.execute(
                    "ALTER TABLE todos ADD COLUMN IF NOT EXISTS user_id INTEGER"
                )
                cur.execute(
                    "ALTER TABLE todos ADD COLUMN IF NOT EXISTS list_id INTEGER REFERENCES todo_lists(id) ON DELETE CASCADE"
                )
                cur.execute(
                    "ALTER TABLE todos ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"
                )
                cur.execute(
                    "ALTER TABLE todos ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES todos(id) ON DELETE CASCADE"
                )
                cur.execute(
                    "ALTER TABLE todos ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0"
                )
                
                # subtasks/checklists table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS todo_items (
                        id SERIAL PRIMARY KEY,
                        todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        done BOOLEAN NOT NULL DEFAULT FALSE,
                        position INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                
                # comments table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS todo_comments (
                        id SERIAL PRIMARY KEY,
                        todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                
                # attachments table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS todo_attachments (
                        id SERIAL PRIMARY KEY,
                        todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER,
                        mime_type TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
    finally:
        pool.putconn(conn)


def _create_pool_with_retry(dsn: str, minconn: int, maxconn: int, retries: int = 30, delay_seconds: float = 1.0) -> SimpleConnectionPool:
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            return SimpleConnectionPool(minconn, maxconn, dsn=dsn)
        except Exception as e:  # psycopg2.OperationalError among others
            last_err = e
            time.sleep(delay_seconds)
    assert last_err is not None
    raise last_err


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))


