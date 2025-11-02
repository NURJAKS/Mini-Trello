import os
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@card_db:5432/card_service')
SQLALCHEMY_TRACK_MODIFICATIONS = False
