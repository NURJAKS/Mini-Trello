import os
import redis
import jwt
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, User, TodoList, Todo, TodoItem, TodoComment, TodoAttachment

# Global variables
redis_client: Optional[redis.Redis] = None

def _parse_bearer(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]

def require_auth(fn):  # type: ignore[no-redef]
    def wrapper(*args, **kwargs):  # type: ignore[no-redef]
        auth_header = request.headers.get("Authorization")
        token = _parse_bearer(auth_header)
        if not token:
            return jsonify({"error": "missing token"}), 401
        
        try:
            payload = jwt.decode(token, os.getenv("JWT_SECRET", "dev_secret"), algorithms=["HS256"])
            if payload.get("type") != "access":
                return jsonify({"error": "invalid token type"}), 401
            
            user_id = int(payload.get("sub", 0))
            if not user_id:
                return jsonify({"error": "invalid token"}), 401
            
            # Check if token is blacklisted in Redis
            if redis_client:
                try:
                    blacklisted = redis_client.get(f"blacklist:{token}")
                    if blacklisted:
                        return jsonify({"error": "token blacklisted"}), 401
                except Exception:
                    pass  # Continue if Redis is unavailable
            
            return fn(user_id=user_id, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "invalid token: Signature has expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"invalid token: {str(e)}"}), 401
        except Exception as e:
            return jsonify({"error": f"auth error: {str(e)}"}), 401
    
    wrapper.__name__ = fn.__name__
    return wrapper

def _issue_tokens(user_id: int) -> Tuple[str, str, str]:
    now = datetime.utcnow()
    access_exp = now + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")))
    refresh_exp = now + timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", "7")))
    
    access_payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": access_exp
    }
    
    refresh_payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": f"{user_id}:{int(now.timestamp())}",
        "iat": now,
        "exp": refresh_exp
    }
    
    secret = os.getenv("JWT_SECRET", "dev_secret")
    access_token = jwt.encode(access_payload, secret, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")
    
    # Store refresh token in Redis
    if redis_client:
        try:
            redis_client.setex(
                f"refresh:{refresh_payload['jti']}", 
                int(os.getenv("REFRESH_TOKEN_DAYS", "7")) * 24 * 3600,
                str(user_id)
            )
        except Exception:
            pass  # Continue if Redis is unavailable
    
    return access_token, refresh_token, refresh_payload["jti"]

def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    
    # Database configuration
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/todo_app")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Redis connection
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()  # Test connection
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️ Redis unavailable: {e}")
        redis_client = None

    # ---------- PUBLIC ENDPOINTS ----------
    @app.get("/")
    def index() -> Any:
        return jsonify({"message": "Todo App API", "version": "2.0"})

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

    @app.post("/api/signup")
    def signup() -> Any:
        data = request.get_json(force=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "email and password required"}), 400

        if len(password) < 6:
            return jsonify({"error": "password must be at least 6 characters"}), 400

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "user already exists"}), 409

        # Create user
        user = User(email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()

        access_token, refresh_token, jti = _issue_tokens(user.id)
        
        print(f"✅ User created: {email}")
        return jsonify({
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "user": user.to_dict()
        }), 201

    @app.post("/api/login")
    def login() -> Any:
        data = request.get_json(force=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "email and password required"}), 400

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({"error": "invalid credentials"}), 401

        access_token, refresh_token, jti = _issue_tokens(user.id)
        
        print(f"✅ User logged in: {email}")
        return jsonify({
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "user": user.to_dict()
        })

    @app.post("/api/refresh")
    def refresh() -> Any:
        data = request.get_json(force=True) or {}
        refresh_token = data.get("refreshToken", "")

        if not refresh_token:
            return jsonify({"error": "refresh token required"}), 400

        try:
            payload = jwt.decode(refresh_token, os.getenv("JWT_SECRET", "dev_secret"), algorithms=["HS256"])
            if payload.get("type") != "refresh":
                return jsonify({"error": "invalid token type"}), 401

            jti = payload.get("jti")
            user_id = int(payload.get("sub", 0))

            # Verify refresh token in Redis
            if redis_client:
                try:
                    stored_user_id = redis_client.get(f"refresh:{jti}")
                    if not stored_user_id or int(stored_user_id) != user_id:
                        return jsonify({"error": "invalid refresh token"}), 401
                except Exception:
                    return jsonify({"error": "token verification failed"}), 401

            # Issue new tokens
            access_token, new_refresh_token, new_jti = _issue_tokens(user_id)

            # Remove old refresh token from Redis
            if redis_client and jti:
                try:
                    redis_client.delete(f"refresh:{jti}")
                except Exception:
                    pass

            return jsonify({
                "accessToken": access_token,
                "refreshToken": new_refresh_token
            })

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "refresh token expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"invalid refresh token: {str(e)}"}), 401

    @app.get("/api/me")
    @require_auth
    def get_me(user_id: int) -> Any:  # type: ignore[override]
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "user not found"}), 404
        return jsonify(user.to_dict())

    # ---------- LISTS ----------
    @app.get("/api/lists")
    @require_auth
    def get_lists(user_id: int) -> Any:  # type: ignore[override]
        lists = TodoList.query.filter_by(user_id=user_id).order_by(TodoList.position).all()
        return jsonify([lst.to_dict() for lst in lists])

    @app.post("/api/lists")
    @require_auth
    def create_list(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        color = data.get("color", "#3B82F6")
        
        if not name:
            return jsonify({"error": "name is required"}), 400
        
        todo_list = TodoList(user_id=user_id, name=name, color=color)
        db.session.add(todo_list)
        db.session.commit()
        
        return jsonify(todo_list.to_dict()), 201

    @app.patch("/api/lists/<int:list_id>")
    @require_auth
    def update_list(list_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        todo_list = TodoList.query.filter_by(id=list_id, user_id=user_id).first()
        
        if not todo_list:
            return jsonify({"error": "list not found"}), 404
        
        if "name" in data:
            todo_list.name = str(data["name"])
        if "color" in data:
            todo_list.color = str(data["color"])
        if "position" in data:
            todo_list.position = int(data["position"])
        
        db.session.commit()
        return jsonify(todo_list.to_dict())

    @app.delete("/api/lists/<int:list_id>")
    @require_auth
    def delete_list(list_id: int, user_id: int) -> Any:  # type: ignore[override]
        todo_list = TodoList.query.filter_by(id=list_id, user_id=user_id).first()
        if not todo_list:
            return jsonify({"error": "list not found"}), 404
        
        db.session.delete(todo_list)
        db.session.commit()
        return "", 204

    # ---------- TODOS ----------
    @app.get("/api/todos")
    @require_auth
    def list_todos(user_id: int) -> Any:  # type: ignore[override]
        search = request.args.get("search", "").strip()
        status = request.args.get("status", "all")
        sort_by = request.args.get("sort", "id")
        list_id = request.args.get("list_id")
        
        query = Todo.query.filter_by(user_id=user_id)
        
        if search:
            query = query.filter(Todo.title.ilike(f"%{search}%"))
        
        if status == "done":
            query = query.filter_by(done=True)
        elif status == "pending":
            query = query.filter_by(done=False)
        
        if list_id:
            query = query.filter_by(list_id=int(list_id))
        
        # Sort
        if sort_by == "title":
            query = query.order_by(Todo.title.asc())
        elif sort_by == "created_at":
            query = query.order_by(Todo.id.asc())
        elif sort_by == "done":
            query = query.order_by(Todo.done.asc(), Todo.id.asc())
        else:  # default by position
            query = query.order_by(Todo.position.asc(), Todo.id.asc())
        
        todos = query.all()
        return jsonify([todo.to_dict() for todo in todos])

    @app.post("/api/todos")
    @require_auth
    def create_todo(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        list_id = data.get("list_id")
        
        if not title:
            return jsonify({"error": "title is required"}), 400

        # If list_id provided, verify it belongs to user
        if list_id:
            todo_list = TodoList.query.filter_by(id=list_id, user_id=user_id).first()
            if not todo_list:
                return jsonify({"error": "list not found"}), 404
        
        todo = Todo(user_id=user_id, list_id=list_id, title=title)
        db.session.add(todo)
        db.session.commit()
        
        return jsonify(todo.to_dict()), 201

    @app.patch("/api/todos/<int:todo_id>")
    @require_auth
    def update_todo(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        if "title" in data:
            todo.title = str(data["title"])
        if "done" in data:
            todo.done = bool(data["done"])
        if "list_id" in data:
            todo.list_id = data["list_id"]
        if "position" in data:
            todo.position = int(data["position"])
        
        db.session.commit()
        return jsonify(todo.to_dict())

    @app.delete("/api/todos/<int:todo_id>")
    @require_auth
    def delete_todo(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        db.session.delete(todo)
        db.session.commit()
        return "", 204

    @app.post("/api/todos/bulk")
    @require_auth
    def bulk_todos(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        action = data.get("action")
        todo_ids = data.get("todo_ids", [])

        if not action or not todo_ids:
            return jsonify({"error": "action and todo_ids required"}), 400

        if action not in ["delete", "mark_done", "mark_pending"]:
            return jsonify({"error": "invalid action"}), 400

        todos = Todo.query.filter(Todo.id.in_(todo_ids), Todo.user_id == user_id).all()
        
        if action == "delete":
            for todo in todos:
                db.session.delete(todo)
        elif action == "mark_done":
            for todo in todos:
                todo.done = True
        elif action == "mark_pending":
            for todo in todos:
                todo.done = False
        
        db.session.commit()
        return jsonify({"affected_count": len(todos), "affected_ids": [t.id for t in todos]})

    @app.post("/api/todos/reorder")
    @require_auth
    def reorder_todos(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        todo_positions = data.get("todo_positions", [])
        
        if not todo_positions:
            return jsonify({"error": "todo_positions required"}), 400
        
        for item in todo_positions:
            todo_id = item.get("id")
            position = item.get("position")
            if todo_id is None or position is None:
                continue
            
            todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
            if todo:
                todo.position = position
        
        db.session.commit()
        return jsonify({"success": True})

    @app.post("/api/todos/move")
    @require_auth
    def move_todo(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        todo_id = data.get("todo_id")
        new_list_id = data.get("new_list_id")
        new_position = data.get("new_position", 0)
        
        if todo_id is None:
            return jsonify({"error": "todo_id required"}), 400
        
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        # If new_list_id provided, verify it belongs to user
        if new_list_id is not None:
            todo_list = TodoList.query.filter_by(id=new_list_id, user_id=user_id).first()
            if not todo_list:
                return jsonify({"error": "list not found"}), 404
        
        todo.list_id = new_list_id
        todo.position = new_position
        db.session.commit()
        
        return jsonify(todo.to_dict())

    @app.post("/api/lists/reorder")
    @require_auth
    def reorder_lists(user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        list_positions = data.get("list_positions", [])
        
        if not list_positions:
            return jsonify({"error": "list_positions required"}), 400
        
        for item in list_positions:
            list_id = item.get("id")
            position = item.get("position")
            if list_id is None or position is None:
                continue
            
            todo_list = TodoList.query.filter_by(id=list_id, user_id=user_id).first()
            if todo_list:
                todo_list.position = position
        
        db.session.commit()
        return jsonify({"success": True})

    # ---------- SUBTASKS/CHECKLISTS ----------
    @app.get("/api/todos/<int:todo_id>/items")
    @require_auth
    def get_todo_items(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        items = TodoItem.query.filter_by(todo_id=todo_id).order_by(TodoItem.position).all()
        return jsonify([item.to_dict() for item in items])

    @app.post("/api/todos/<int:todo_id>/items")
    @require_auth
    def create_todo_item(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        item = TodoItem(todo_id=todo_id, title=title)
        db.session.add(item)
        db.session.commit()
        
        return jsonify(item.to_dict()), 201

    # ---------- COMMENTS ----------
    @app.get("/api/todos/<int:todo_id>/comments")
    @require_auth
    def get_todo_comments(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        comments = db.session.query(TodoComment, User).join(
            User, TodoComment.user_id == User.id
        ).filter(TodoComment.todo_id == todo_id).order_by(TodoComment.created_at).all()
        
        result = []
        for comment, user in comments:
            result.append({
                "id": comment.id,
                "content": comment.content,
                "created_at": comment.created_at.isoformat(),
                "author_email": user.email
            })
        
        return jsonify(result)

    @app.post("/api/todos/<int:todo_id>/comments")
    @require_auth
    def create_todo_comment(todo_id: int, user_id: int) -> Any:  # type: ignore[override]
        data = request.get_json(force=True) or {}
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"error": "content is required"}), 400
        
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        if not todo:
            return jsonify({"error": "todo not found"}), 404
        
        comment = TodoComment(todo_id=todo_id, user_id=user_id, content=content)
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat()
        }), 201

    # ---------- DEBUG ENDPOINTS ----------
    @app.get("/debug/db")
    def debug_db() -> Any:
        try:
            user_count = User.query.count()
            list_count = TodoList.query.count()
            todo_count = Todo.query.count()
            return jsonify({
                "users": user_count,
                "lists": list_count,
                "todos": todo_count,
                "status": "connected"
            })
        except Exception as e:
            return jsonify({"error": str(e), "status": "error"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
