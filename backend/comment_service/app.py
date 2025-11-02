import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Comment
from celery_worker import send_notification

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@comment_db:5432/comment_service')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    Migrate(app, db)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'comment_service'})

    @app.route('/api/comments', methods=['GET'])
    def get_comments():
        card_id = request.args.get('card_id')
        comments = Comment.query.filter_by(card_id=card_id).order_by(Comment.created_at).all()
        return jsonify([c.to_dict() for c in comments])

    @app.route('/api/comments', methods=['POST'])
    def create_comment():
        data = request.get_json(force=True) or {}
        card_id = data.get('card_id')
        user_id = data.get('user_id')
        content = (data.get('content') or '').strip()
        if not card_id or not user_id or not content:
            return jsonify({'error': 'card_id, user_id, content required'}), 400
        comment = Comment(card_id=card_id, user_id=user_id, content=content)
        db.session.add(comment)
        db.session.commit()
        # Async notification example
        recipient_email = data.get('recipient_email') or 'simulate@example.com'
        send_notification.delay(recipient_email, f'New comment: {content}')
        return jsonify(comment.to_dict()), 201

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5004)
