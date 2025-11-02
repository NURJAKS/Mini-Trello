from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, nullable=False) # link to card/todo
    user_id = db.Column(db.Integer, nullable=False) # author (from user_service)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'card_id': self.card_id,
            'user_id': self.user_id,
            'content': self.content,
            'created_at': self.created_at.isoformat()
        }
