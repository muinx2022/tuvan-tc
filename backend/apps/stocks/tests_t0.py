from __future__ import annotations

from datetime import date, datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.settings_app import services as setting_services
from apps.stocks import t0_snapshot_service as t0s
from apps.stocks.models import StockT0RealtimeState, StockT0Snapshot


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


class T0SnapshotPersistenceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        t0s._ensure_t0_tables()

    def setUp(self):
        StockT0RealtimeState.objects.all().delete()
        StockT0Snapshot.objects.all().delete()

    def test_snapshot_upsert_keeps_single_row_per_slot(self):
        trading_date = date(2026, 3, 24)
        t0s.upsert_realtime_state(
            "SSI",
            {"s": "SSI", "tvt": 1_000_000, "gta": 25_500_000_000},
            trading_date=trading_date,
        )

        first = t0s.snapshot_due_realtime_states("09:15", timezone.now(), trading_date)
        t0s.upsert_realtime_state(
            "SSI",
            {"s": "SSI", "tvt": 2_000_000, "gta": 50_000_000_000},
            trading_date=trading_date,
        )
        second = t0s.snapshot_due_realtime_states("09:15", timezone.now(), trading_date)

        self.assertEqual(first["count"], 1)
        self.assertEqual(second["count"], 1)
        self.assertEqual(StockT0Snapshot.objects.count(), 1)
        snapshot = StockT0Snapshot.objects.get(ticker="SSI", trading_date=trading_date, snapshot_slot="09:15")
        self.assertEqual(snapshot.total_match_vol, 2_000_000)

    def test_list_valid_t0_tickers_filters_non_three_letter_codes(self):
        fake_qs = ["SSI", "VN30F1M", "abc", "HCM", "A1C", "VIX"]
        with mock.patch.object(t0s.StockSymbol.objects, "order_by") as mocked_order_by:
            mocked_order_by.return_value.values_list.return_value.distinct.return_value = fake_qs
            self.assertEqual(t0s.list_valid_t0_tickers(), ["SSI", "ABC", "HCM", "VIX"])
