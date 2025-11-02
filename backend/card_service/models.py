from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Card(db.Model):
    __tablename__ = 'cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    list_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'done': self.done,
            'created_at': self.created_at.isoformat(),
            'list_id': self.list_id,
            'user_id': self.user_id,
            'position': self.position
        }

class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'done': self.done,
            'position': self.position,
            'card_id': self.card_id
        }
