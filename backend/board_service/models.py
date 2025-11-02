from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class TodoList(db.Model):
    __tablename__ = 'todo_lists'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # From user_service
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#3B82F6', nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'position': self.position,
            'user_id': self.user_id
        }
