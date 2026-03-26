from django.apps import AppConfig
import os
import sys


class StocksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stocks"
    label = "stocks"

    def ready(self):
        if any(arg in sys.argv for arg in ("test", "makemigrations", "migrate", "collectstatic")):
            return
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return
        from apps.stocks.history_sync_scheduler import start_scheduler

        start_scheduler()
