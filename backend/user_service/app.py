import os
import redis
import jwt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, User

JWT_SECRET = os.getenv('JWT_SECRET', 'dev_super_secret_change_me')
ACCESS_TOKEN_MINUTES = int(os.getenv('ACCESS_TOKEN_MINUTES', '15'))
REFRESH_TOKEN_DAYS = int(os.getenv('REFRESH_TOKEN_DAYS', '7'))
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

redis_client = None

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@user_db:5432/user_service')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    Migrate(app, db)

    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
    except Exception:
        redis_client = None

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'user_service'})

    def _issue_tokens(user_id):
        now = datetime.utcnow()
        access_payload = {
            'sub': str(user_id),
            'type': 'access',
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
        }
        refresh_jti = f'{user_id}:{int(now.timestamp())}'
        refresh_payload = {
            'sub': str(user_id),
            'type': 'refresh',
            'jti': refresh_jti,
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(days=REFRESH_TOKEN_DAYS)).timestamp()),
        }
        access_token = jwt.encode(access_payload, JWT_SECRET, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm='HS256')
        if redis_client:
            try:
                redis_client.setex(f'refresh:{refresh_jti}', REFRESH_TOKEN_DAYS * 24 * 3600, str(user_id))
            except Exception:
                pass
        return access_token, refresh_token, refresh_jti

    def _parse_bearer(auth_header):
        if not auth_header:
            return None
        parts = auth_header.split()
        return parts[1] if len(parts) == 2 and parts[0].lower() == 'bearer' else None

    def require_auth(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _parse_bearer(request.headers.get('Authorization'))
            if not token:
                return jsonify({'error': 'missing bearer token'}), 401
            try:
                data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
                if data.get('type') != 'access':
                    return jsonify({'error': 'invalid token type'}), 401
                user_id = int(data.get('sub'))
            except Exception as e:
                return jsonify({'error': f'invalid token: {e}'}), 401
            return fn(user_id=user_id, *args, **kwargs)
        return wrapper

    @app.route('/api/signup', methods=['POST'])
    def signup():
        payload = request.get_json(force=True) or {}
        email = (payload.get('email') or '').strip().lower()
        password = payload.get('password') or ''
        if not email or not password:
            return jsonify({'error': 'email and password required'}), 400
        if len(password) < 6:
            return jsonify({'error': 'password must be at least 6 characters'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'email already registered'}), 409
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        access, refresh, _ = _issue_tokens(user.id)
        return jsonify({'accessToken': access, 'refreshToken': refresh, 'user': user.to_dict()})

    @app.route('/api/login', methods=['POST'])
    def login():
        payload = request.get_json(force=True) or {}
        email = (payload.get('email') or '').strip().lower()
        password = payload.get('password') or ''
        if not email or not password:
            return jsonify({'error': 'email and password required'}), 400
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({'error': 'invalid credentials'}), 401
        access, refresh, _ = _issue_tokens(user.id)
        return jsonify({'accessToken': access, 'refreshToken': refresh, 'user': user.to_dict()})

    @app.route('/api/refresh', methods=['POST'])
    def refresh():
        payload = request.get_json(force=True) or {}
        token = payload.get('refreshToken')
        if not token:
            return jsonify({'error': 'refreshToken required'}), 400
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            if data.get('type') != 'refresh':
                return jsonify({'error': 'invalid token type'}), 401
            jti = data.get('jti')
            # Optionally check Redis.
            uid = redis_client.get(f'refresh:{jti}') if redis_client else None
            if uid is None:
                return jsonify({'error': 'refresh expired or revoked'}), 401
            user_id = int(uid)
        except Exception as e:
            return jsonify({'error': f'invalid token: {e}'}), 401
        access, refresh_new, _ = _issue_tokens(user_id)
        return jsonify({'accessToken': access, 'refreshToken': refresh_new})

    @app.route('/api/me', methods=['GET'])
    @require_auth
    def me(user_id):
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'user not found'}), 404
        return jsonify(user.to_dict())

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001)
