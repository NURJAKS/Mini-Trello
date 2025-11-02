import os

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@user_db:5432/user_service')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
SQLALCHEMY_TRACK_MODIFICATIONS = False
JWT_SECRET = os.getenv('JWT_SECRET', 'dev_super_secret_change_me')
