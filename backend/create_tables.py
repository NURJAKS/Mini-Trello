#!/usr/bin/env python3

import os
import sys
sys.path.append('.')

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Create Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/todo_app")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class TodoList(db.Model):
    __tablename__ = 'todo_lists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#3B82F6', nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Todo(db.Model):
    __tablename__ = 'todos'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    list_id = db.Column(db.Integer, db.ForeignKey('todo_lists.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=True)
    position = db.Column(db.Integer, default=0, nullable=False)

class TodoItem(db.Model):
    __tablename__ = 'todo_items'
    
    id = db.Column(db.Integer, primary_key=True)
    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class TodoComment(db.Model):
    __tablename__ = 'todo_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class TodoAttachment(db.Model):
    __tablename__ = 'todo_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

if __name__ == '__main__':
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✅ Database tables created successfully!")
        
        # Check if tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📊 Created tables: {', '.join(tables)}")
