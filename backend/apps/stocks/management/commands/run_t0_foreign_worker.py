from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.stocks.t0_foreign_sync_service import T0ForeignSyncWorker
from common.exceptions import BadRequestError


class Command(BaseCommand):
    help = "Run SSI board foreign intraday sync worker"

    def handle(self, *args, **options):
        try:
            T0ForeignSyncWorker().run_forever()
        except BadRequestError as ex:
            self.stdout.write(self.style.WARNING(f"Skip starting T0 foreign worker: {ex}"))
