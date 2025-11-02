FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --upgrade pip
RUN pip install flask flask_sqlalchemy flask-migrate flask-cors psycopg2-binary celery
EXPOSE 5004
CMD ["python", "app.py"]
