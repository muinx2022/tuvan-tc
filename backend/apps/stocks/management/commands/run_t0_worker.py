from __future__ import annotations

import asyncio

from django.core.management.base import BaseCommand

from apps.stocks.t0_snapshot_service import DnseT0Worker
from common.exceptions import BadRequestError


class Command(BaseCommand):
    help = "Run DNSE T0 websocket worker"

    def handle(self, *args, **options):
        try:
            asyncio.run(DnseT0Worker().run_forever())
        except BadRequestError as ex:
            self.stdout.write(self.style.WARNING(f"Skip starting T0 worker: {ex}"))
