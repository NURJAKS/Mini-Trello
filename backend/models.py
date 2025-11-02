from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    todo_lists = db.relationship('TodoList', backref='user', lazy=True, cascade='all, delete-orphan')
    todos = db.relationship('Todo', backref='user', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('TodoComment', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password: str) -> None:
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'email': self.email,
            'createdAt': self.created_at.isoformat()
        }

class TodoList(db.Model):
    __tablename__ = 'todo_lists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#3B82F6', nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    todos = db.relationship('Todo', backref='todo_list', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'position': self.position
        }

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
    
    # Relationships
    children = db.relationship('Todo', backref=db.backref('parent', remote_side=[id]), lazy=True)
    items = db.relationship('TodoItem', backref='todo', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('TodoComment', backref='todo', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('TodoAttachment', backref='todo', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'done': self.done,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'list_id': self.list_id,
            'position': self.position
        }

class TodoItem(db.Model):
    __tablename__ = 'todo_items'
    
    id = db.Column(db.Integer, primary_key=True)
    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'done': self.done,
            'position': self.position
        }

class TodoComment(db.Model):
    __tablename__ = 'todo_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'author_email': self.user.email
        }

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
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'created_at': self.created_at.isoformat()
        }
