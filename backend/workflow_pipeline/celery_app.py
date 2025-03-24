from celery import Celery
import os

app = Celery(
    'tasks',
    broker=os.getenv("REDIS_URL"),
    include=["backend.workflow_pipeline.scheduler"]
)