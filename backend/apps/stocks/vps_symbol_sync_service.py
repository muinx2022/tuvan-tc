from __future__ import annotations

from collections.abc import Callable

from django.utils import timezone

from apps.stocks.models import StockIndustryGroup, StockSymbol
from apps.stocks.vps_client import VpsClient
from apps.stocks.vps_parser import ParsedVpsSymbol, parse_company_basic_payload

SAVE_BATCH_SIZE = 200


def _sync_industry_groups(rows: list[ParsedVpsSymbol]) -> dict[str, StockIndustryGroup]:
    names = sorted({row.industry_name.strip() for row in rows if row.industry_name and row.industry_name.strip()})
    if not names:
        return {}
    existing = {group.name: group for group in StockIndustryGroup.objects.filter(name__in=names)}
    now = timezone.now()
    to_create = [StockIndustryGroup(name=name, created_at=now, updated_at=now) for name in names if name not in existing]
    if to_create:
        StockIndustryGroup.objects.bulk_create(to_create, batch_size=SAVE_BATCH_SIZE)
        existing.update({group.name: group for group in StockIndustryGroup.objects.filter(name__in=[item.name for item in to_create])})
    return existing


def sync_from_vps(update_status: Callable[[bool, int, int, int, int, str, str | None], None], client: VpsClient | None = None) -> dict:
    http = client or VpsClient()
    update_status(True, 0, 0, 0, 0, "Downloading data from VPS", None)

    root = http.fetch_company_basic()
    rows, received = parse_company_basic_payload(root)
    total_unique = len(rows)
    industry_by_name = _sync_industry_groups(rows)

    update_status(True, received, total_unique, 0, 0, "Saving symbols to database", None)

    existing_symbols = {
        symbol.ticker.upper(): symbol
        for symbol in StockSymbol.objects.filter(ticker__in=[row.ticker for row in rows])
    }
    to_create: list[StockSymbol] = []
    to_update: list[StockSymbol] = []
    processed = 0
    synced = 0
    now = timezone.now()

    for row in rows:
        symbol = existing_symbols.get(row.ticker)
        is_create = symbol is None
        if symbol is None:
            symbol = StockSymbol(ticker=row.ticker)
        symbol.organ_code = row.organ_code
        symbol.organ_name = row.organ_name
        symbol.organ_short_name = row.organ_short_name
        symbol.icb_code = row.icb_code
        symbol.icb_name2 = row.industry_name
        symbol.industry_group = industry_by_name.get(row.industry_name.strip()) if row.industry_name and row.industry_name.strip() else None
        symbol.listing_date = row.listing_date
        symbol.updated_at = now
        if is_create:
            to_create.append(symbol)
        else:
            to_update.append(symbol)
        processed += 1

        if len(to_create) >= SAVE_BATCH_SIZE:
            StockSymbol.objects.bulk_create(to_create, batch_size=SAVE_BATCH_SIZE)
            synced += len(to_create)
            to_create.clear()
            update_status(True, received, total_unique, processed, synced, "Syncing", None)
        if len(to_update) >= SAVE_BATCH_SIZE:
            StockSymbol.objects.bulk_update(
                to_update,
                ["organ_code", "organ_name", "organ_short_name", "icb_code", "icb_name2", "industry_group", "listing_date", "updated_at"],
                batch_size=SAVE_BATCH_SIZE,
            )
            synced += len(to_update)
            to_update.clear()
            update_status(True, received, total_unique, processed, synced, "Syncing", None)
        elif processed % 25 == 0:
            update_status(True, received, total_unique, processed, synced, "Syncing", None)

    if to_create:
        StockSymbol.objects.bulk_create(to_create, batch_size=SAVE_BATCH_SIZE)
        synced += len(to_create)
    if to_update:
        StockSymbol.objects.bulk_update(
            to_update,
            ["organ_code", "organ_name", "organ_short_name", "icb_code", "icb_name2", "industry_group", "listing_date", "updated_at"],
            batch_size=SAVE_BATCH_SIZE,
        )
        synced += len(to_update)

    update_status(False, received, total_unique, processed, synced, "Completed", None)
    return {"received": received, "synced": synced}
