import os
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@comment_db:5432/comment_service')
SQLALCHEMY_TRACK_MODIFICATIONS = False
