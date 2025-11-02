from celery import Celery
import os

celery = Celery(
    'comment_service',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@rabbitmq:5672//'),
    backend='rpc://'
)

@celery.task
def send_notification(email, message):
    # placeholder: integrate with real email or notification system
    print(f"Sending notification to {email}: {message}")
