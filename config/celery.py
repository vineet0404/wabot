import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("wabot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Har 10 minute me due reminders dekho (docker-compose ki 'beat' service chalni chahiye)
app.conf.beat_schedule = {
    "send-due-reminders": {
        "task": "apps.bookings.tasks.send_due_reminders_task",
        "schedule": 600.0,
    },
}
