from __future__ import annotations

import json
import uuid

import requests
from django.conf import settings as dj_settings
from django.db import connection
from django.db import transaction
from django.utils import timezone

from apps.settings_app.models import AppSetting, DnseSetting, MediaSetting
from common.exceptions import BadRequestError

APP_SETTING_GOOGLE_OAUTH = "google_oauth"
APP_SETTING_HISTORY_SYNC_SCHEDULE = "history_sync_schedule"
APP_SETTING_HISTORY_SYNC_RUNTIME = "history_sync_runtime"
APP_SETTING_T0_SNAPSHOT_SCHEDULE = "t0_snapshot_schedule"
APP_SETTING_T0_WORKER_STATUS = "t0_worker_status"
APP_SETTING_T0_WORKER_LOCK = "t0_worker_lock"
APP_SETTING_T0_FOREIGN_WORKER_LOCK = "t0_foreign_worker_lock"
APP_SETTING_SSI_FC = "ssi_fc"
APP_SETTING_FOREIGN_BACKFILL_RUNTIME = "foreign_backfill_runtime"
APP_SETTING_FOREIGN_BACKFILL_LOCK = "foreign_backfill_lock"
APP_SETTING_MONEY_FLOW_FEATURES = "money_flow_features"
DEFAULT_T0_SNAPSHOT_TIMES = [
    "09:15",
    "09:30",
    "09:45",
    "10:00",
    "10:15",
    "10:30",
    "10:45",
    "11:00",
    "11:15",
    "11:30",
    "13:00",
    "13:15",
    "13:30",
    "13:45",
    "14:00",
    "14:15",
    "14:30",
    "14:45",
    "15:00",
]
DEFAULT_T0_PROJECTION_SLOTS = list(DEFAULT_T0_SNAPSHOT_TIMES)
DEFAULT_T0_FOREIGN_START_TIME = "09:15"
DEFAULT_T0_FOREIGN_END_TIME = "15:00"


def _ensure_app_settings_table() -> None:
    vendor = connection.vendor
    if vendor == "postgresql":
        sql = """
        CREATE TABLE IF NOT EXISTS app_settings (
            id BIGSERIAL PRIMARY KEY,
            setting_key VARCHAR(255) NOT NULL UNIQUE,
            setting_value TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    else:
        sql = """
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key VARCHAR(255) NOT NULL UNIQUE,
            setting_value TEXT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    with connection.cursor() as cursor:
        cursor.execute(sql)


def _get_app_setting_entity(setting_key: str) -> AppSetting | None:
    _ensure_app_settings_table()
    return AppSetting.objects.filter(setting_key=setting_key).first()


def _get_app_setting_json(setting_key: str, default: dict | None = None) -> dict:
    entity = _get_app_setting_entity(setting_key)
    if not entity or not (entity.setting_value or "").strip():
        return dict(default or {})
    try:
        loaded = json.loads(entity.setting_value)
    except json.JSONDecodeError:
        return dict(default or {})
    return loaded if isinstance(loaded, dict) else dict(default or {})


@transaction.atomic
def _save_app_setting_json(setting_key: str, value: dict) -> dict:
    _ensure_app_settings_table()
    now = timezone.now()
    entity = AppSetting.objects.filter(setting_key=setting_key).first()
    if entity:
        entity.setting_value = json.dumps(value, ensure_ascii=False)
        entity.updated_at = now
        entity.save(update_fields=["setting_value", "updated_at"])
        return value
    AppSetting.objects.create(
        setting_key=setting_key,
        setting_value=json.dumps(value, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    return value


def _media_defaults() -> MediaSetting:
    base = dj_settings.APP_MEDIA_PUBLIC_BASE_URL.rstrip("/")
    now = timezone.now()
    return MediaSetting(
        provider="cloudinary",
        local_root_path="uploads",
        local_public_base_url=f"{base}/api/v1/public/media",
        created_at=now,
        updated_at=now,
    )


def get_media_entity() -> MediaSetting:
    m = MediaSetting.objects.order_by("id").first()
    if m:
        return m
    d = _media_defaults()
    d.save(force_insert=True)
    return d


def media_to_dict(m: MediaSetting) -> dict:
    return {
        "id": m.id,
        "provider": (m.provider or "cloudinary").lower(),
        "localRootPath": m.local_root_path,
        "localPublicBaseUrl": m.local_public_base_url,
        "cloudinaryCloudName": m.cloudinary_cloud_name,
        "cloudinaryApiKey": m.cloudinary_api_key,
        "cloudinaryApiSecret": m.cloudinary_api_secret,
        "cloudinaryFolder": m.cloudinary_folder,
        "cloudflareS3Endpoint": m.cloudflare_s3_endpoint,
        "cloudflareS3AccessKey": m.cloudflare_s3_access_key,
        "cloudflareS3SecretKey": m.cloudflare_s3_secret_key,
        "cloudflareS3Bucket": m.cloudflare_s3_bucket,
        "cloudflareS3Region": m.cloudflare_s3_region,
        "cloudflareS3PublicBaseUrl": m.cloudflare_s3_public_base_url,
        "updatedAt": m.updated_at.isoformat() if m.updated_at else None,
    }


def _is_cloudinary_configured(m: MediaSetting) -> bool:
    return bool(m.cloudinary_cloud_name and m.cloudinary_api_key and m.cloudinary_api_secret)


def _is_s3_configured(m: MediaSetting) -> bool:
    return bool(m.cloudflare_s3_endpoint and m.cloudflare_s3_access_key and m.cloudflare_s3_secret_key and m.cloudflare_s3_bucket)


def resolve_upload_provider(m: MediaSetting) -> str:
    p = (m.provider or "cloudinary").lower()
    if p == "cloudinary" and _is_cloudinary_configured(m):
        return "cloudinary"
    if p in ("cloudflare_s3", "cloudflare-s3", "cloudflares3") and _is_s3_configured(m):
        return "cloudflare_s3"
    return "local"


@transaction.atomic
def save_media(data: dict) -> dict:
    m = get_media_entity()
    prov = (data.get("provider") or "cloudinary").lower()
    m.provider = prov
    m.local_root_path = (data.get("localRootPath") or data.get("local_root_path") or "uploads").strip()
    base = dj_settings.APP_MEDIA_PUBLIC_BASE_URL.rstrip("/")
    m.local_public_base_url = (
        (data.get("localPublicBaseUrl") or data.get("local_public_base_url") or "").strip()
        or f"{base}/api/v1/public/media"
    )
    m.cloudinary_cloud_name = data.get("cloudinaryCloudName") or data.get("cloudinary_cloud_name")
    m.cloudinary_api_key = data.get("cloudinaryApiKey") or data.get("cloudinary_api_key")
    m.cloudinary_api_secret = data.get("cloudinaryApiSecret") or data.get("cloudinary_api_secret")
    m.cloudinary_folder = data.get("cloudinaryFolder") or data.get("cloudinary_folder")
    m.cloudflare_s3_endpoint = data.get("cloudflareS3Endpoint") or data.get("cloudflare_s3_endpoint")
    m.cloudflare_s3_access_key = data.get("cloudflareS3AccessKey") or data.get("cloudflare_s3_access_key")
    m.cloudflare_s3_secret_key = data.get("cloudflareS3SecretKey") or data.get("cloudflare_s3_secret_key")
    m.cloudflare_s3_bucket = data.get("cloudflareS3Bucket") or data.get("cloudflare_s3_bucket")
    m.cloudflare_s3_region = data.get("cloudflareS3Region") or data.get("cloudflare_s3_region")
    m.cloudflare_s3_public_base_url = data.get("cloudflareS3PublicBaseUrl") or data.get("cloudflare_s3_public_base_url")
    m.updated_at = timezone.now()
    if prov == "cloudinary" and not _is_cloudinary_configured(m):
        raise BadRequestError("Cloudinary settings are incomplete")
    if prov in ("cloudflare_s3", "cloudflare-s3") and not _is_s3_configured(m):
        raise BadRequestError("Cloudflare S3 settings are incomplete")
    m.save()
    return media_to_dict(m)


def get_dnse_entity() -> DnseSetting:
    d = DnseSetting.objects.order_by("id").first()
    if d:
        return d
    now = timezone.now()
    d = DnseSetting(created_at=now, updated_at=now)
    d.save(force_insert=True)
    return d


def get_ssi_fc_config() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_SSI_FC,
        default={
            "consumerId": "",
            "consumerSecret": "",
        },
    )
    return {
        "consumerId": str(data.get("consumerId") or ""),
        "consumerSecret": str(data.get("consumerSecret") or ""),
    }


@transaction.atomic
def save_ssi_fc(data: dict) -> dict:
    payload = {
        "consumerId": (data.get("consumerId") or data.get("consumer_id") or "").strip(),
        "consumerSecret": (data.get("consumerSecret") or data.get("consumer_secret") or "").strip(),
    }
    _save_app_setting_json(APP_SETTING_SSI_FC, payload)
    return get_ssi_fc_config()


def dnse_to_dict(d: DnseSetting) -> dict:
    return {
        "id": d.id,
        "apiKey": d.api_key,
        "apiSecret": d.api_secret,
        "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
    }


@transaction.atomic
def save_dnse(data: dict) -> dict:
    d = get_dnse_entity()
    d.api_key = data.get("apiKey") or data.get("api_key")
    d.api_secret = data.get("apiSecret") or data.get("api_secret")
    d.updated_at = timezone.now()
    d.save()
    return dnse_to_dict(d)


def get_google_oauth_config() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_GOOGLE_OAUTH,
        default={
            "enabled": False,
            "clientId": "",
            "clientSecret": "",
        },
    )
    return {
        "enabled": bool(data.get("enabled", False)),
        "clientId": str(data.get("clientId") or ""),
        "clientSecret": str(data.get("clientSecret") or ""),
    }


@transaction.atomic
def save_google_oauth(data: dict) -> dict:
    payload = {
        "enabled": bool(data.get("enabled", False)),
        "clientId": (data.get("clientId") or data.get("client_id") or "").strip(),
        "clientSecret": (data.get("clientSecret") or data.get("client_secret") or "").strip(),
    }
    if payload["enabled"] and not payload["clientId"]:
        raise BadRequestError("Google OAuth client ID is required when enabled")
    _save_app_setting_json(APP_SETTING_GOOGLE_OAUTH, payload)
    return get_google_oauth_config()


def get_google_oauth_runtime_config() -> dict:
    stored = get_google_oauth_config()
    env_client_id = (dj_settings.APP_GOOGLE_CLIENT_ID or "").strip()
    if stored["enabled"] and stored["clientId"]:
        return {
            "enabled": True,
            "clientId": stored["clientId"],
            "clientSecret": stored["clientSecret"],
            "source": "db",
        }
    if env_client_id:
        return {
            "enabled": True,
            "clientId": env_client_id,
            "clientSecret": "",
            "source": "env",
        }
    return {
        "enabled": False,
        "clientId": "",
        "clientSecret": "",
        "source": "none",
    }


def get_history_sync_schedule_config() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_HISTORY_SYNC_SCHEDULE,
        default={
            "enabled": False,
            "hour": 0,
            "minute": 0,
        },
    )
    try:
        hour = int(data.get("hour", 0))
    except (TypeError, ValueError):
        hour = 0
    try:
        minute = int(data.get("minute", 0))
    except (TypeError, ValueError):
        minute = 0
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return {
        "enabled": bool(data.get("enabled", False)),
        "hour": hour,
        "minute": minute,
    }


def get_history_sync_schedule_settings() -> dict:
    return {
        **get_history_sync_schedule_config(),
        "runtime": get_history_sync_runtime(),
    }


@transaction.atomic
def save_history_sync_schedule(data: dict) -> dict:
    current = get_history_sync_schedule_config()
    try:
        hour = int(data.get("hour", 0))
    except (TypeError, ValueError):
        raise BadRequestError("Hour must be between 0 and 23")
    try:
        minute = int(data.get("minute", 0))
    except (TypeError, ValueError):
        raise BadRequestError("Minute must be between 0 and 59")
    if hour < 0 or hour > 23:
        raise BadRequestError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise BadRequestError("Minute must be between 0 and 59")
    payload = {
        "enabled": bool(data.get("enabled", False)),
        "hour": hour,
        "minute": minute,
    }
    _save_app_setting_json(APP_SETTING_HISTORY_SYNC_SCHEDULE, payload)
    if payload != current:
        save_history_sync_runtime(
            {
                "lastAttemptedDate": None,
                "lastError": None,
            }
        )
    return get_history_sync_schedule_config()


def get_history_sync_runtime() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_HISTORY_SYNC_RUNTIME,
        default={
            "lastAttemptedDate": None,
            "lastStartedAt": None,
            "lastError": None,
        },
    )
    return {
        "lastAttemptedDate": data.get("lastAttemptedDate"),
        "lastStartedAt": data.get("lastStartedAt"),
        "lastError": data.get("lastError"),
    }


@transaction.atomic
def save_history_sync_runtime(data: dict) -> dict:
    current = get_history_sync_runtime()
    payload = {
        **current,
        **data,
    }
    _save_app_setting_json(APP_SETTING_HISTORY_SYNC_RUNTIME, payload)
    return get_history_sync_runtime()


def _normalize_t0_time(value: object) -> str:
    raw = str(value or "").strip()
    parts = raw.split(":")
    if len(parts) != 2:
        raise BadRequestError("T0 snapshot times must use HH:mm format")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except (TypeError, ValueError) as ex:
        raise BadRequestError("T0 snapshot times must use HH:mm format") from ex
    if hour < 0 or hour > 23:
        raise BadRequestError("T0 snapshot hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise BadRequestError("T0 snapshot minute must be between 0 and 59")
    return f"{hour:02d}:{minute:02d}"


def _normalize_t0_snapshot_times(values: object) -> list[str]:
    if values in (None, ""):
        return []
    if not isinstance(values, list):
        raise BadRequestError("T0 snapshot times must be a list")
    normalized = sorted({_normalize_t0_time(value) for value in values})
    return normalized


def _normalize_positive_int(value: object, default: int, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed <= 0:
        raise BadRequestError(f"{label} must be > 0")
    return parsed


def _normalize_weight(value: object, default: float, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 0:
        raise BadRequestError(f"{label} must be >= 0")
    return parsed


def get_t0_snapshot_schedule_config() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_T0_SNAPSHOT_SCHEDULE,
        default={
            "enabled": False,
            "times": DEFAULT_T0_SNAPSHOT_TIMES,
            "foreignRefreshMinutes": 15,
            "foreignStartTime": DEFAULT_T0_FOREIGN_START_TIME,
            "foreignEndTime": DEFAULT_T0_FOREIGN_END_TIME,
            "projectionSlots": DEFAULT_T0_PROJECTION_SLOTS,
            "projectionWindow20": 20,
            "projectionWindow5": 5,
            "projectionWeight20": 0.6,
            "projectionWeight5": 0.4,
            "projectionFinalSlot": "15:00",
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )
    normalized_times = _normalize_t0_snapshot_times(data.get("times") or DEFAULT_T0_SNAPSHOT_TIMES)
    normalized_projection_slots = _normalize_t0_snapshot_times(data.get("projectionSlots") or DEFAULT_T0_PROJECTION_SLOTS)
    return {
        "enabled": bool(data.get("enabled", False)),
        "times": normalized_times,
        "foreignRefreshMinutes": _normalize_positive_int(data.get("foreignRefreshMinutes", 15), 15, "foreignRefreshMinutes"),
        "foreignStartTime": _normalize_t0_time(data.get("foreignStartTime") or DEFAULT_T0_FOREIGN_START_TIME),
        "foreignEndTime": _normalize_t0_time(data.get("foreignEndTime") or DEFAULT_T0_FOREIGN_END_TIME),
        "projectionSlots": normalized_projection_slots,
        "projectionWindow20": _normalize_positive_int(data.get("projectionWindow20", 20), 20, "projectionWindow20"),
        "projectionWindow5": _normalize_positive_int(data.get("projectionWindow5", 5), 5, "projectionWindow5"),
        "projectionWeight20": _normalize_weight(data.get("projectionWeight20", 0.6), 0.6, "projectionWeight20"),
        "projectionWeight5": _normalize_weight(data.get("projectionWeight5", 0.4), 0.4, "projectionWeight5"),
        "projectionFinalSlot": _normalize_t0_time(data.get("projectionFinalSlot") or "15:00"),
        "timezone": "Asia/Ho_Chi_Minh",
    }


@transaction.atomic
def save_t0_snapshot_schedule(data: dict) -> dict:
    current = get_t0_snapshot_schedule_config()
    raw_enabled = data.get("enabled", current.get("enabled", False))
    raw_times = data.get("times", current.get("times") or DEFAULT_T0_SNAPSHOT_TIMES)
    raw_foreign_refresh_minutes = data.get("foreignRefreshMinutes", current.get("foreignRefreshMinutes", 15))
    raw_foreign_start_time = data.get("foreignStartTime", current.get("foreignStartTime", DEFAULT_T0_FOREIGN_START_TIME))
    raw_foreign_end_time = data.get("foreignEndTime", current.get("foreignEndTime", DEFAULT_T0_FOREIGN_END_TIME))
    raw_projection_slots = data.get("projectionSlots", current.get("projectionSlots") or DEFAULT_T0_PROJECTION_SLOTS)
    raw_projection_window20 = data.get("projectionWindow20", current.get("projectionWindow20", 20))
    raw_projection_window5 = data.get("projectionWindow5", current.get("projectionWindow5", 5))
    raw_projection_final_slot = data.get("projectionFinalSlot", current.get("projectionFinalSlot", "15:00"))

    weight20 = _normalize_weight(data.get("projectionWeight20", current.get("projectionWeight20", 0.6)), 0.6, "projectionWeight20")
    weight5 = _normalize_weight(data.get("projectionWeight5", current.get("projectionWeight5", 0.4)), 0.4, "projectionWeight5")
    if weight20 == 0 and weight5 == 0:
        raise BadRequestError("At least one projection weight must be > 0")

    normalized_times = _normalize_t0_snapshot_times(raw_times or current.get("times") or DEFAULT_T0_SNAPSHOT_TIMES)
    normalized_projection_slots = _normalize_t0_snapshot_times(raw_projection_slots or current.get("projectionSlots") or DEFAULT_T0_PROJECTION_SLOTS)

    payload = {
        "enabled": bool(raw_enabled),
        "times": normalized_times,
        "foreignRefreshMinutes": _normalize_positive_int(raw_foreign_refresh_minutes, 15, "foreignRefreshMinutes"),
        "foreignStartTime": _normalize_t0_time(raw_foreign_start_time or DEFAULT_T0_FOREIGN_START_TIME),
        "foreignEndTime": _normalize_t0_time(raw_foreign_end_time or DEFAULT_T0_FOREIGN_END_TIME),
        "projectionSlots": normalized_projection_slots,
        "projectionWindow20": _normalize_positive_int(raw_projection_window20, 20, "projectionWindow20"),
        "projectionWindow5": _normalize_positive_int(raw_projection_window5, 5, "projectionWindow5"),
        "projectionWeight20": weight20,
        "projectionWeight5": weight5,
        "projectionFinalSlot": _normalize_t0_time(raw_projection_final_slot or "15:00"),
        "timezone": "Asia/Ho_Chi_Minh",
    }
    _save_app_setting_json(APP_SETTING_T0_SNAPSHOT_SCHEDULE, payload)
    return get_t0_snapshot_schedule_config()


def get_t0_worker_status() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_T0_WORKER_STATUS,
        default={
            "running": False,
            "connected": False,
            "phase": "Idle",
            "subscribedCount": 0,
            "subscribedTickers": 0,
            "lastMessageAt": None,
            "lastSnapshotAt": None,
            "lastSnapshotSlot": None,
            "lastSnapshotCount": 0,
            "lastError": None,
            "ssiForeignPhase": None,
            "lastForeignSyncAt": None,
            "nextForeignSyncAt": None,
            "foreignRefreshMinutes": 15,
            "foreignStartTime": DEFAULT_T0_FOREIGN_START_TIME,
            "foreignEndTime": DEFAULT_T0_FOREIGN_END_TIME,
            "dnseKeyMasked": None,
            "connectionStartedAt": None,
            "authSuccessAt": None,
            "lastReconnectAt": None,
            "reconnectCount": 0,
            "updatedAt": None,
        },
    )
    return {
        "running": bool(data.get("running", False)),
        "connected": bool(data.get("connected", False)),
        "phase": str(data.get("phase") or "Idle"),
        "subscribedCount": int(data.get("subscribedCount", 0) or 0),
        "subscribedTickers": int(data.get("subscribedTickers", 0) or 0),
        "lastMessageAt": data.get("lastMessageAt"),
        "lastSnapshotAt": data.get("lastSnapshotAt"),
        "lastSnapshotSlot": data.get("lastSnapshotSlot"),
        "lastSnapshotCount": int(data.get("lastSnapshotCount", 0) or 0),
        "lastError": data.get("lastError"),
        "ssiForeignPhase": data.get("ssiForeignPhase"),
        "lastForeignSyncAt": data.get("lastForeignSyncAt"),
        "nextForeignSyncAt": data.get("nextForeignSyncAt"),
        "foreignRefreshMinutes": int(data.get("foreignRefreshMinutes", 15) or 15),
        "foreignStartTime": data.get("foreignStartTime") or DEFAULT_T0_FOREIGN_START_TIME,
        "foreignEndTime": data.get("foreignEndTime") or DEFAULT_T0_FOREIGN_END_TIME,
        "dnseKeyMasked": data.get("dnseKeyMasked"),
        "connectionStartedAt": data.get("connectionStartedAt"),
        "authSuccessAt": data.get("authSuccessAt"),
        "lastReconnectAt": data.get("lastReconnectAt"),
        "reconnectCount": int(data.get("reconnectCount", 0) or 0),
        "updatedAt": data.get("updatedAt"),
    }


@transaction.atomic
def save_t0_worker_status(data: dict) -> dict:
    current = get_t0_worker_status()
    merged = {
        **current,
        **data,
        "updatedAt": timezone.now().isoformat(),
    }
    _save_app_setting_json(APP_SETTING_T0_WORKER_STATUS, merged)
    return get_t0_worker_status()


def get_t0_worker_lock() -> dict:
    return _get_app_setting_json(APP_SETTING_T0_WORKER_LOCK, default={})


@transaction.atomic
def save_t0_worker_lock(data: dict) -> dict:
    _save_app_setting_json(APP_SETTING_T0_WORKER_LOCK, data)
    return get_t0_worker_lock()


def get_t0_foreign_worker_lock() -> dict:
    return _get_app_setting_json(APP_SETTING_T0_FOREIGN_WORKER_LOCK, default={})


@transaction.atomic
def save_t0_foreign_worker_lock(data: dict) -> dict:
    _save_app_setting_json(APP_SETTING_T0_FOREIGN_WORKER_LOCK, data)
    return get_t0_foreign_worker_lock()


def get_money_flow_feature_config() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_MONEY_FLOW_FEATURES,
        default={
            "historyBaselineDays": 10,
            "historyMinDaysForStable": 3,
            "historyAllowPartialBaseline": True,
            "intradaySlotMode": "strict_same_slot",
            "lowHistoryConfidenceMode": "flag_only",
        },
    )
    baseline_days = _normalize_positive_int(data.get("historyBaselineDays", 10), 10, "historyBaselineDays")
    min_days = _normalize_positive_int(data.get("historyMinDaysForStable", 3), 3, "historyMinDaysForStable")
    if min_days > baseline_days:
        min_days = baseline_days
    intraday_slot_mode = str(data.get("intradaySlotMode") or "strict_same_slot").strip() or "strict_same_slot"
    if intraday_slot_mode != "strict_same_slot":
        intraday_slot_mode = "strict_same_slot"
    low_history_confidence_mode = str(data.get("lowHistoryConfidenceMode") or "flag_only").strip() or "flag_only"
    if low_history_confidence_mode != "flag_only":
        low_history_confidence_mode = "flag_only"
    return {
        "historyBaselineDays": baseline_days,
        "historyMinDaysForStable": min_days,
        "historyAllowPartialBaseline": bool(data.get("historyAllowPartialBaseline", True)),
        "intradaySlotMode": intraday_slot_mode,
        "lowHistoryConfidenceMode": low_history_confidence_mode,
    }


@transaction.atomic
def save_money_flow_feature_config(data: dict) -> dict:
    current = get_money_flow_feature_config()
    baseline_days = _normalize_positive_int(data.get("historyBaselineDays", current.get("historyBaselineDays", 10)), 10, "historyBaselineDays")
    min_days = _normalize_positive_int(data.get("historyMinDaysForStable", current.get("historyMinDaysForStable", 3)), 3, "historyMinDaysForStable")
    if min_days > baseline_days:
        raise BadRequestError("historyMinDaysForStable must be <= historyBaselineDays")
    intraday_slot_mode = str(data.get("intradaySlotMode", current.get("intradaySlotMode", "strict_same_slot")) or "strict_same_slot").strip()
    if intraday_slot_mode != "strict_same_slot":
        raise BadRequestError("intradaySlotMode must be strict_same_slot")
    low_history_confidence_mode = str(data.get("lowHistoryConfidenceMode", current.get("lowHistoryConfidenceMode", "flag_only")) or "flag_only").strip()
    if low_history_confidence_mode != "flag_only":
        raise BadRequestError("lowHistoryConfidenceMode must be flag_only")
    payload = {
        "historyBaselineDays": baseline_days,
        "historyMinDaysForStable": min_days,
        "historyAllowPartialBaseline": bool(data.get("historyAllowPartialBaseline", current.get("historyAllowPartialBaseline", True))),
        "intradaySlotMode": intraday_slot_mode,
        "lowHistoryConfidenceMode": low_history_confidence_mode,
    }
    _save_app_setting_json(APP_SETTING_MONEY_FLOW_FEATURES, payload)
    return get_money_flow_feature_config()


def get_foreign_backfill_runtime() -> dict:
    data = _get_app_setting_json(
        APP_SETTING_FOREIGN_BACKFILL_RUNTIME,
        default={
            "running": False,
            "phase": "Idle",
            "targetDate": None,
            "completedDate": None,
            "lastAttemptAt": None,
            "lastCompletedAt": None,
            "lastQuality": None,
            "lastResult": None,
            "lastError": None,
            "updatedAt": None,
        },
    )
    return {
        "running": bool(data.get("running", False)),
        "phase": str(data.get("phase") or "Idle"),
        "targetDate": data.get("targetDate"),
        "completedDate": data.get("completedDate"),
        "lastAttemptAt": data.get("lastAttemptAt"),
        "lastCompletedAt": data.get("lastCompletedAt"),
        "lastQuality": data.get("lastQuality"),
        "lastResult": data.get("lastResult"),
        "lastError": data.get("lastError"),
        "updatedAt": data.get("updatedAt"),
    }


@transaction.atomic
def save_foreign_backfill_runtime(data: dict) -> dict:
    current = get_foreign_backfill_runtime()
    merged = {
        **current,
        **data,
        "updatedAt": timezone.now().isoformat(),
    }
    _save_app_setting_json(APP_SETTING_FOREIGN_BACKFILL_RUNTIME, merged)
    return get_foreign_backfill_runtime()


def get_foreign_backfill_lock() -> dict:
    return _get_app_setting_json(APP_SETTING_FOREIGN_BACKFILL_LOCK, default={})


@transaction.atomic
def save_foreign_backfill_lock(data: dict) -> dict:
    _save_app_setting_json(APP_SETTING_FOREIGN_BACKFILL_LOCK, data)
    return get_foreign_backfill_lock()


def _asset_type(content_type: str | None) -> str:
    if not content_type:
        return "raw"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    return "raw"


def upload_media(file, folder: str | None) -> dict:
    from pathlib import Path

    m = get_media_entity()
    prov = resolve_upload_provider(m)
    orig = file.name or "upload"
    ext = orig.rsplit(".", 1)[-1].lower() if "." in orig else ""
    fname = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())

    if prov == "local":
        root = Path(m.local_root_path or "uploads")
        root.mkdir(parents=True, exist_ok=True)
        dest = root / fname
        with open(dest, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)
        base = (m.local_public_base_url or "").rstrip("/")
        url = f"{base}/{fname}"
        return {
            "provider": "local",
            "assetType": _asset_type(getattr(file, "content_type", None)),
            "url": url,
            "publicId": fname,
            "originalFilename": orig,
            "contentType": getattr(file, "content_type", None),
            "size": getattr(file, "size", None),
        }

    if prov == "cloudinary":
        if not _is_cloudinary_configured(m):
            raise BadRequestError("Cloudinary settings are incomplete")
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=m.cloudinary_cloud_name,
            api_key=m.cloudinary_api_key,
            api_secret=m.cloudinary_api_secret,
        )
        asset = _asset_type(getattr(file, "content_type", None))
        opts = {}
        if folder and str(folder).strip():
            opts["folder"] = str(folder).strip()
        if m.cloudinary_folder:
            opts["folder"] = m.cloudinary_folder.strip()
        try:
            result = cloudinary.uploader.upload(file, **opts)
        except Exception as ex:
            raise BadRequestError(f"Cloudinary upload failed: {ex}") from ex
        return {
            "provider": "cloudinary",
            "assetType": asset,
            "url": result.get("secure_url") or result.get("url"),
            "publicId": result.get("public_id"),
            "originalFilename": orig,
            "contentType": getattr(file, "content_type", None),
            "size": getattr(file, "size", None),
        }

    # S3 placeholder
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=m.cloudflare_s3_endpoint,
            aws_access_key_id=m.cloudflare_s3_access_key,
            aws_secret_access_key=m.cloudflare_s3_secret_key,
            region_name=m.cloudflare_s3_region or "auto",
        )
        bucket = m.cloudflare_s3_bucket or ""
        key = f"{folder.strip()}/{fname}" if folder else fname
        extra = {"ContentType": getattr(file, "content_type", "application/octet-stream")}
        s3.upload_fileobj(file, bucket, key, ExtraArgs=extra)
        pub = (m.cloudflare_s3_public_base_url or "").rstrip("/")
        url = f"{pub}/{key}" if pub else f"{m.cloudflare_s3_endpoint}/{bucket}/{key}"
        return {
            "provider": "cloudflare_s3",
            "assetType": _asset_type(getattr(file, "content_type", None)),
            "url": url,
            "publicId": key,
            "originalFilename": orig,
            "contentType": getattr(file, "content_type", None),
            "size": getattr(file, "size", None),
        }
    except Exception as ex:
        raise BadRequestError(f"S3 upload failed: {ex}") from ex
