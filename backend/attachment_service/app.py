import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Attachment

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@attachment_db:5432/attachment_service')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    Migrate(app, db)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'attachment_service'})

    @app.route('/api/attachments', methods=['GET'])
    def get_attachments():
        card_id = request.args.get('card_id')
        attachments = Attachment.query.filter_by(card_id=card_id).order_by(Attachment.created_at).all()
        return jsonify([a.to_dict() for a in attachments])

    @app.route('/api/attachments', methods=['POST'])
    def create_attachment():
        data = request.get_json(force=True) or {}
        card_id = data.get('card_id')
        filename = data.get('filename')
        original_filename = data.get('original_filename')
        file_size = data.get('file_size')
        mime_type = data.get('mime_type')
        file_path = data.get('file_path')
        if not (card_id and filename and original_filename and mime_type and file_path and file_size):
            return jsonify({'error': 'all fields required'}), 400
        attachment = Attachment(card_id=card_id, filename=filename, original_filename=original_filename, file_size=file_size, mime_type=mime_type, file_path=file_path)
        db.session.add(attachment)
        db.session.commit()
        return jsonify(attachment.to_dict()), 201

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5005)
