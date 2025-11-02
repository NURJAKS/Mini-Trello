from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    def to_dict(self):
        return {
            'id': self.id,
            'card_id': self.card_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'file_path': self.file_path,
            'created_at': self.created_at.isoformat()
        }
