import os

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@board_db:5432/board_service')
SQLALCHEMY_TRACK_MODIFICATIONS = False
