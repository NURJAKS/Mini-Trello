import os
from flask_migrate import Migrate
from models import db
from app_sqlalchemy import create_app

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
