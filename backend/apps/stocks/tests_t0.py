from __future__ import annotations

from datetime import date, datetime
from unittest import mock

from django.test import TestCase
from django.db import connection
from django.utils import timezone

from apps.settings_app import services as setting_services
from apps.stocks import money_flow_service as mfs
from apps.stocks import t0_snapshot_service as t0s
from apps.stocks.models import MoneyFlowDailyClose, MoneyFlowFeatureSnapshot, StockHistory, StockIndustryGroup, StockSymbol, StockT0RealtimeState, StockT0Snapshot


class T0SnapshotScheduleTests(TestCase):
    def test_save_schedule_sorts_and_deduplicates(self):
        payload = setting_services.save_t0_snapshot_schedule(
            {
                "enabled": True,
                "times": ["14:30", "09:15", "09:15", "10:00"],
            }
        )

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["times"], ["09:15", "10:00", "14:30"])
        self.assertEqual(payload["timezone"], "Asia/Ho_Chi_Minh")

    def test_slot_due_only_within_grace_window(self):
        now = datetime(2026, 3, 24, 10, 1, tzinfo=t0s.T0_TIMEZONE)

        self.assertTrue(t0s._slot_due(now, "10:00", set()))
        self.assertFalse(t0s._slot_due(now, "09:15", set()))
        self.assertFalse(t0s._slot_due(now, "10:00", {"10:00"}))

    def test_save_money_flow_feature_config_validates_min_days(self):
        payload = setting_services.save_money_flow_feature_config({"historyBaselineDays": 12, "historyMinDaysForStable": 4})
        self.assertEqual(payload["historyBaselineDays"], 12)
        self.assertEqual(payload["historyMinDaysForStable"], 4)


class T0SnapshotPersistenceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        datetime_type = "TIMESTAMPTZ" if connection.vendor == "postgresql" else "DATETIME"
        auto_id = "BIGSERIAL PRIMARY KEY" if connection.vendor == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        symbol_id = "BIGSERIAL PRIMARY KEY" if connection.vendor == "postgresql" else "INTEGER PRIMARY KEY"
        industry_id = "BIGSERIAL PRIMARY KEY" if connection.vendor == "postgresql" else "INTEGER PRIMARY KEY"
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS stock_industry_groups (
                    id {industry_id},
                    name VARCHAR(255) NOT NULL UNIQUE,
                    created_at {datetime_type} NOT NULL,
                    updated_at {datetime_type} NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS stock_symbols (
                    id {symbol_id},
                    ticker VARCHAR(20) NOT NULL UNIQUE,
                    organ_code VARCHAR(50) NULL,
                    organ_name VARCHAR(255) NULL,
                    organ_short_name VARCHAR(120) NULL,
                    icb_code VARCHAR(50) NULL,
                    icb_name2 VARCHAR(255) NULL,
                    industry_group_id INTEGER NULL,
                    listing_date VARCHAR(50) NULL,
                    updated_at {datetime_type} NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS stock_histories (
                    id {auto_id},
                    ticker VARCHAR(20) NOT NULL,
                    trading_date DATE NOT NULL,
                    open_price NUMERIC(18,4) NULL,
                    high_price NUMERIC(18,4) NULL,
                    low_price NUMERIC(18,4) NULL,
                    close_price NUMERIC(18,4) NULL,
                    volume BIGINT NULL,
                    avg_price NUMERIC(18,4) NULL,
                    price_changed NUMERIC(18,4) NULL,
                    per_price_change NUMERIC(18,4) NULL,
                    total_match_vol BIGINT NULL,
                    total_match_val NUMERIC(18,4) NULL,
                    foreign_buy_vol_total BIGINT NULL,
                    foreign_sell_vol_total BIGINT NULL,
                    raw_payload TEXT NULL,
                    created_at {datetime_type} NOT NULL
                )
                """
            )
        t0s._ensure_t0_tables()
        mfs._ensure_money_flow_tables()

    def setUp(self):
        StockT0RealtimeState.objects.all().delete()
        StockT0Snapshot.objects.all().delete()
        MoneyFlowDailyClose.objects.all().delete()
        MoneyFlowFeatureSnapshot.objects.all().delete()
        StockHistory.objects.all().delete()
        StockSymbol.objects.all().delete()
        StockIndustryGroup.objects.all().delete()

    def test_snapshot_upsert_keeps_single_row_per_slot(self):
        trading_date = date(2026, 3, 24)
        t0s.upsert_realtime_state(
            "SSI",
            {"s": "SSI", "tvt": 1_000_000, "gta": 25_500_000_000, "side": 1, "quantity": 1000, "price": 25.5},
            trading_date=trading_date,
        )

        first = t0s.snapshot_due_realtime_states("09:15", timezone.now(), trading_date)
        t0s.upsert_realtime_state(
            "SSI",
            {"s": "SSI", "tvt": 2_000_000, "gta": 50_000_000_000, "side": 2, "quantity": 500, "price": 26},
            trading_date=trading_date,
        )
        second = t0s.snapshot_due_realtime_states("09:15", timezone.now(), trading_date)

        self.assertEqual(first["count"], 1)
        self.assertEqual(second["count"], 1)
        self.assertEqual(StockT0Snapshot.objects.count(), 1)
        snapshot = StockT0Snapshot.objects.get(ticker="SSI", trading_date=trading_date, snapshot_slot="09:15")
        self.assertEqual(snapshot.total_match_vol, 2_000_000)
        self.assertEqual(snapshot.active_buy_vol, 1000)
        self.assertEqual(snapshot.active_sell_vol, 500)

    def test_upsert_realtime_state_accumulates_trade_extra_by_side(self):
        trading_date = date(2026, 3, 24)
        t0s.upsert_realtime_state(
            "SSI",
            {"symbol": "SSI", "totalVolumeTraded": 1000, "grossTradeAmount": "2.55", "side": 1, "quantity": 1000, "price": 25.5},
            trading_date=trading_date,
        )
        payload = t0s.upsert_realtime_state(
            "SSI",
            {"symbol": "SSI", "totalVolumeTraded": 1500, "grossTradeAmount": "3.85", "side": 2, "quantity": 500, "price": 26},
            trading_date=trading_date,
        )

        self.assertEqual(payload["totalMatchVol"], 1500)
        self.assertEqual(payload["activeBuyVol"], 1000)
        self.assertEqual(payload["activeSellVol"], 500)
        self.assertEqual(payload["activeNetVol"], 500)
        self.assertEqual(str(payload["activeBuyVal"]), "2.5500")
        self.assertEqual(str(payload["activeSellVal"]), "1.3000")
        self.assertEqual(str(payload["activeNetVal"]), "1.2500")

    def test_list_valid_t0_tickers_filters_non_three_letter_codes(self):
        fake_qs = ["SSI", "VN30F1M", "abc", "HCM", "A1C", "VIX"]
        with mock.patch.object(t0s.StockSymbol.objects, "order_by") as mocked_order_by:
            mocked_order_by.return_value.values_list.return_value.distinct.return_value = fake_qs
            self.assertEqual(t0s.list_valid_t0_tickers(), ["SSI", "ABC", "HCM", "VIX"])

    def test_capture_money_flow_daily_close_uses_latest_snapshot_of_day(self):
        trading_date = date(2026, 3, 24)
        now = timezone.now()
        StockT0Snapshot.objects.create(
            ticker="SSI",
            trading_date=trading_date,
            snapshot_slot="14:00",
            snapshot_at=now,
            total_match_vol=1000,
            total_match_val="10.0000",
            active_buy_vol=600,
            active_sell_vol=200,
            active_buy_val="6.0000",
            active_sell_val="2.0000",
            created_at=now,
            updated_at=now,
        )
        StockT0Snapshot.objects.create(
            ticker="SSI",
            trading_date=trading_date,
            snapshot_slot="15:00",
            snapshot_at=now,
            total_match_vol=1200,
            total_match_val="12.0000",
            active_buy_vol=700,
            active_sell_vol=250,
            active_buy_val="7.5000",
            active_sell_val="2.5000",
            created_at=now,
            updated_at=now,
        )
        result = mfs.capture_money_flow_daily_close(trading_date)
        self.assertEqual(result["count"], 1)
        entity = MoneyFlowDailyClose.objects.get(ticker="SSI", trading_date=trading_date)
        self.assertEqual(entity.snapshot_slot, "15:00")
        self.assertEqual(str(entity.net_flow_val), "5.0000")

    def test_rebuild_money_flow_slot_features_uses_same_slot_history(self):
        trading_date = date(2026, 3, 24)
        industry = StockIndustryGroup.objects.create(id=1, name="Chung khoan", created_at=timezone.now(), updated_at=timezone.now())
        StockSymbol.objects.create(id=1, ticker="SSI", industry_group=industry, updated_at=timezone.now())
        StockSymbol.objects.create(id=2, ticker="HCM", industry_group=industry, updated_at=timezone.now())
        now = timezone.now()
        for previous_date, buy_val, sell_val in [
            (date(2026, 3, 23), "6.0000", "2.0000"),
            (date(2026, 3, 22), "5.0000", "3.0000"),
            (date(2026, 3, 21), "4.0000", "3.0000"),
        ]:
            StockT0Snapshot.objects.create(
                ticker="SSI",
                trading_date=previous_date,
                snapshot_slot="10:00",
                snapshot_at=now,
                total_match_vol=1000,
                total_match_val="10.0000",
                active_buy_vol=0,
                active_sell_vol=0,
                active_buy_val=buy_val,
                active_sell_val=sell_val,
                created_at=now,
                updated_at=now,
            )
        MoneyFlowFeatureSnapshot.objects.create(
            entity_type="market",
            entity_id="GLOBAL",
            trading_date=date(2026, 3, 23),
            window_type="slot",
            snapshot_slot="10:00",
            as_of_at=now,
            feature_payload='{"marketNetFlowVal":"6.0000"}',
            history_days_used=1,
            history_baseline_days=10,
            history_min_days_for_stable=3,
            low_history_confidence=False,
            created_at=now,
            updated_at=now,
        )
        MoneyFlowFeatureSnapshot.objects.create(
            entity_type="sector",
            entity_id="1",
            trading_date=date(2026, 3, 23),
            window_type="slot",
            snapshot_slot="10:00",
            as_of_at=now,
            feature_payload='{"sectorNetFlowVal":"5.0000"}',
            history_days_used=1,
            history_baseline_days=10,
            history_min_days_for_stable=3,
            low_history_confidence=False,
            created_at=now,
            updated_at=now,
        )
        StockT0Snapshot.objects.create(
            ticker="SSI",
            trading_date=trading_date,
            snapshot_slot="10:00",
            snapshot_at=now,
            total_match_vol=1500,
            total_match_val="15.0000",
            active_buy_vol=900,
            active_sell_vol=300,
            active_buy_val="9.0000",
            active_sell_val="3.0000",
            created_at=now,
            updated_at=now,
        )
        StockT0Snapshot.objects.create(
            ticker="HCM",
            trading_date=trading_date,
            snapshot_slot="10:00",
            snapshot_at=now,
            total_match_vol=1000,
            total_match_val="10.0000",
            active_buy_vol=400,
            active_sell_vol=200,
            active_buy_val="4.0000",
            active_sell_val="2.0000",
            created_at=now,
            updated_at=now,
        )
        result = mfs.rebuild_money_flow_slot_features("10:00", trading_date)
        self.assertEqual(result["stocks"], 2)
        stock_feature = MoneyFlowFeatureSnapshot.objects.get(
            entity_type="stock",
            entity_id="SSI",
            trading_date=trading_date,
            window_type="slot",
            snapshot_slot="10:00",
        )
        payload = stock_feature.feature_payload
        self.assertIn('"netFlowRatioSlot"', payload)
        self.assertIn('"stockVsMarketStrengthSlot"', payload)

    def test_backfill_money_flow_eod_builds_daily_close_and_eod_features(self):
        trading_date = date(2026, 3, 25)
        industry = StockIndustryGroup.objects.create(id=1, name="Chung khoan", created_at=timezone.now(), updated_at=timezone.now())
        StockSymbol.objects.create(id=1, ticker="SSI", industry_group=industry, updated_at=timezone.now())
        now = timezone.now()
        StockT0Snapshot.objects.create(
            ticker="SSI",
            trading_date=trading_date,
            snapshot_slot="15:00",
            snapshot_at=now,
            total_match_vol=1200,
            total_match_val="12.0000",
            active_buy_vol=700,
            active_sell_vol=250,
            active_buy_val="7.5000",
            active_sell_val="2.5000",
            created_at=now,
            updated_at=now,
        )
        StockHistory.objects.create(
            ticker="SSI",
            trading_date=trading_date,
            total_match_vol=1200,
            total_match_val="12.0000",
            created_at=now,
        )

        result = mfs.backfill_money_flow_eod(trading_date, trading_date)

        self.assertEqual(result["totalDates"], 1)
        self.assertEqual(MoneyFlowDailyClose.objects.filter(trading_date=trading_date).count(), 1)
        self.assertEqual(MoneyFlowFeatureSnapshot.objects.filter(trading_date=trading_date, window_type="eod").count(), 3)

    def test_backfill_money_flow_slot_builds_features_for_existing_slots(self):
        trading_date = date(2026, 3, 26)
        industry = StockIndustryGroup.objects.create(id=1, name="Chung khoan", created_at=timezone.now(), updated_at=timezone.now())
        StockSymbol.objects.create(id=1, ticker="SSI", industry_group=industry, updated_at=timezone.now())
        now = timezone.now()
        StockT0Snapshot.objects.create(
            ticker="SSI",
            trading_date=trading_date,
            snapshot_slot="10:00",
            snapshot_at=now,
            total_match_vol=1200,
            total_match_val="12.0000",
            active_buy_vol=700,
            active_sell_vol=250,
            active_buy_val="7.5000",
            active_sell_val="2.5000",
            created_at=now,
            updated_at=now,
        )

        result = mfs.backfill_money_flow_slot(trading_date, trading_date)

        self.assertEqual(result["totalDates"], 1)
        self.assertEqual(result["totalSlots"], 1)
        self.assertEqual(MoneyFlowFeatureSnapshot.objects.filter(trading_date=trading_date, window_type="slot", snapshot_slot="10:00").count(), 3)
