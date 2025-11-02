import os
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@attachment_db:5432/attachment_service')
SQLALCHEMY_TRACK_MODIFICATIONS = False
