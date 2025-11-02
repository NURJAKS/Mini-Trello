import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Card, ChecklistItem

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@card_db:5432/card_service')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    Migrate(app, db)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'card_service'})

    @app.route('/api/cards', methods=['GET'])
    def get_cards():
        user_id = request.args.get('user_id')
        cards = Card.query.filter_by(user_id=user_id).order_by(Card.position).all()
        return jsonify([c.to_dict() for c in cards])

    @app.route('/api/cards', methods=['POST'])
    def create_card():
        data = request.get_json(force=True) or {}
        user_id = data.get('user_id')
        list_id = data.get('list_id')
        title = (data.get('title') or '').strip()
        if not user_id or not list_id or not title:
            return jsonify({'error': 'user_id, list_id, title required'}), 400
        card = Card(user_id=user_id, list_id=list_id, title=title)
        db.session.add(card)
        db.session.commit()
        return jsonify(card.to_dict()), 201

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5003)
