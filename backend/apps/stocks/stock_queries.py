"""Raw SQL aligned with StockHistoryRepository JPA queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import connection


def aggregate_industry_daily(industry_group_id: int | None) -> list[dict]:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT
                h.trading_date,
                COALESCE(SUM(h.total_match_val), 0) AS total_match_val,
                COALESCE(SUM(h.total_match_vol), 0) AS total_match_vol
            FROM stock_histories h
            JOIN stock_symbols s ON s.ticker = h.ticker
            WHERE (%s IS NULL OR s.industry_group_id = %s)
            GROUP BY h.trading_date
            ORDER BY h.trading_date ASC
            """,
            [industry_group_id, industry_group_id],
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def aggregate_ticker_daily(ticker: str) -> list[dict]:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT
                h.trading_date,
                COALESCE(SUM(h.total_match_val), 0) AS total_match_val,
                COALESCE(SUM(h.total_match_vol), 0) AS total_match_vol
            FROM stock_histories h
            WHERE h.ticker = %s
            GROUP BY h.trading_date
            ORDER BY h.trading_date ASC
            """,
            [ticker],
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def aggregate_industry_allocation_daily() -> list[dict]:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT
                h.trading_date,
                s.industry_group_id,
                g.name AS industry_group_name,
                COALESCE(SUM(h.total_match_val), 0) AS total_match_val
            FROM stock_histories h
            JOIN stock_symbols s ON s.ticker = h.ticker
            LEFT JOIN stock_industry_groups g ON g.id = s.industry_group_id
            GROUP BY h.trading_date, s.industry_group_id, g.name
            ORDER BY h.trading_date ASC
            """
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def aggregate_ticker_allocation_by_industry(industry_group_id: int) -> list[dict]:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT
                h.trading_date,
                h.ticker,
                COALESCE(SUM(h.total_match_val), 0) AS total_match_val
            FROM stock_histories h
            JOIN stock_symbols s ON s.ticker = h.ticker
            WHERE s.industry_group_id = %s
            GROUP BY h.trading_date, h.ticker
            ORDER BY h.trading_date ASC
            """,
            [industry_group_id],
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def aggregate_ticker_allocation_by_icb(icb_code: str) -> list[dict]:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT
                h.trading_date,
                h.ticker,
                COALESCE(SUM(h.total_match_val), 0) AS total_match_val
            FROM stock_histories h
            JOIN stock_symbols s ON s.ticker = h.ticker
            WHERE UPPER(s.icb_code) = UPPER(%s)
            GROUP BY h.trading_date, h.ticker
            ORDER BY h.trading_date ASC
            """,
            [icb_code],
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def find_eligible_finance_chart_tickers(min_avg_volume: int) -> list[dict]:
    with connection.cursor() as c:
        c.execute(
            """
            WITH ranked AS (
                SELECT
                    s.id AS stock_symbol_id,
                    UPPER(s.ticker) AS ticker,
                    COALESCE(h.total_match_vol, 0) AS total_match_vol,
                    ROW_NUMBER() OVER (PARTITION BY UPPER(s.ticker) ORDER BY h.trading_date DESC) AS rn
                FROM stock_histories h
                JOIN stock_symbols s ON UPPER(s.ticker) = UPPER(h.ticker)
                WHERE char_length(trim(s.ticker)) = 3
            )
            SELECT
                r.stock_symbol_id,
                r.ticker
            FROM ranked r
            WHERE r.rn <= 20
            GROUP BY r.stock_symbol_id, r.ticker
            HAVING COUNT(*) = 20 AND AVG(r.total_match_vol) >= %s
            ORDER BY COALESCE(
                MAX(
                    (SELECT MAX(snap.updated_at)
                     FROM stock_finance_chart_snapshots snap
                     WHERE UPPER(snap.ticker) = r.ticker)
                ),
                to_timestamp(0)
            ) ASC, r.ticker ASC
            """,
            [min_avg_volume],
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def get_eligible_finance_chart_progress(min_avg_volume: int) -> dict:
    with connection.cursor() as c:
        c.execute(
            """
            WITH ranked AS (
                SELECT
                    s.id AS stock_symbol_id,
                    UPPER(s.ticker) AS ticker,
                    COALESCE(h.total_match_vol, 0) AS total_match_vol,
                    ROW_NUMBER() OVER (PARTITION BY UPPER(s.ticker) ORDER BY h.trading_date DESC) AS rn
                FROM stock_histories h
                JOIN stock_symbols s ON UPPER(s.ticker) = UPPER(h.ticker)
                WHERE char_length(trim(s.ticker)) = 3
            ),
            eligible AS (
                SELECT
                    r.stock_symbol_id,
                    r.ticker
                FROM ranked r
                WHERE r.rn <= 20
                GROUP BY r.stock_symbol_id, r.ticker
                HAVING COUNT(*) = 20 AND AVG(r.total_match_vol) >= %s
            ),
            existing AS (
                SELECT DISTINCT UPPER(ticker) AS ticker
                FROM stock_finance_chart_snapshots
            )
            SELECT
                COUNT(*) AS total_eligible_count,
                COUNT(existing.ticker) AS existing_count
            FROM eligible
            LEFT JOIN existing ON existing.ticker = eligible.ticker
            """,
            [min_avg_volume],
        )
        row = c.fetchone() or (0, 0)
        return {
            "totalEligibleCount": int(row[0] or 0),
            "existingCount": int(row[1] or 0),
        }


def search_ticker_summaries(ticker_filter: str) -> list[dict]:
    tf = (ticker_filter or "").strip().upper()
    with connection.cursor() as c:
        if not tf:
            c.execute(
                """
                SELECT
                    s.stock_symbol_id,
                    UPPER(s.ticker) AS ticker,
                    COUNT(*) AS chart_count,
                    array_to_string(array_agg(DISTINCT s.report_type ORDER BY s.report_type), ',') AS report_types,
                    MAX(s.updated_at) AS last_synced_at
                FROM stock_finance_chart_snapshots s
                GROUP BY s.stock_symbol_id, UPPER(s.ticker)
                ORDER BY UPPER(s.ticker) ASC
                """
            )
        else:
            c.execute(
                """
                SELECT
                    s.stock_symbol_id,
                    UPPER(s.ticker) AS ticker,
                    COUNT(*) AS chart_count,
                    array_to_string(array_agg(DISTINCT s.report_type ORDER BY s.report_type), ',') AS report_types,
                    MAX(s.updated_at) AS last_synced_at
                FROM stock_finance_chart_snapshots s
                WHERE UPPER(s.ticker) LIKE %s
                GROUP BY s.stock_symbol_id, UPPER(s.ticker)
                ORDER BY UPPER(s.ticker) ASC
                """,
                [f"%{tf}%"],
            )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def industry_key(row) -> str:
    gid = row.get("industry_group_id")
    name = row.get("industry_group_name") or ""
    if gid is not None:
        return f"{gid}::{name}"
    return f"null::{name}"


def pct(part: Decimal, total: Decimal) -> Decimal:
    if total is None or total == 0:
        return Decimal("0")
    return (part / total * Decimal("100")).quantize(Decimal("0.01"))
