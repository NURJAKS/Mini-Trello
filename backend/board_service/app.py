import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, TodoList

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@board_db:5432/board_service')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    Migrate(app, db)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'board_service'})

    @app.route('/api/lists', methods=['GET'])
    def get_lists():
        user_id = request.args.get('user_id')  # In real scenario, via JWT and Kong plugin
        lists = TodoList.query.filter_by(user_id=user_id).order_by(TodoList.position).all()
        return jsonify([lst.to_dict() for lst in lists])

    @app.route('/api/lists', methods=['POST'])
    def create_list():
        data = request.get_json(force=True) or {}
        user_id = data.get('user_id')
        name = (data.get('name') or '').strip()
        color = data.get('color', '#3B82F6')
        if not name or not user_id:
            return jsonify({'error': 'user_id and name required'}), 400
        todo_list = TodoList(user_id=user_id, name=name, color=color)
        db.session.add(todo_list)
        db.session.commit()
        return jsonify(todo_list.to_dict()), 201

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5002)
