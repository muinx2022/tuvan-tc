from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.stocks.foreign_backfill_service import ForeignBackfillWorker
from common.exceptions import BadRequestError


class Command(BaseCommand):
    help = "Run foreign data backfill worker"

    def handle(self, *args, **options):
        try:
            ForeignBackfillWorker().run_forever()
        except BadRequestError as ex:
            self.stdout.write(self.style.WARNING(f"Skip starting foreign backfill worker: {ex}"))
