from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.stock_finance.models import StockFinanceChartAssessment, StockFinanceChartSnapshot
from apps.stocks.models import StockSymbol
from common.exceptions import BadRequestError, NotFoundError


@dataclass
class MetricPoint:
    term: str
    value: float
    unit: str | None


@dataclass
class CompanyProfile:
    ticker: str
    industry_group_name: str | None
    icb_name2: str | None
    profile_type: str


def _term_rank(term: str | None) -> int:
    if not term:
        return -999999
    term = str(term).strip()
    try:
        if term.startswith("Q"):
            quarter, year = term.split("/")
            return int(year) * 10 + int(quarter[1:])
        if term.startswith("N/"):
            return int(term[2:]) * 10 + 9
    except Exception:
        return -999999
    return -999999


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _normalize_text(value: str | None) -> str:
    raw = (value or "").strip().lower()
    normalized = unicodedata.normalize("NFD", raw)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(stripped.split())


def _load_series_by_name(ticker: str) -> dict[str, list[MetricPoint]]:
    series: dict[str, list[MetricPoint]] = {}
    rows = StockFinanceChartSnapshot.objects.filter(ticker__iexact=ticker, report_type__in=["QUARTER", "YEAR"])
    for snapshot in rows:
        try:
            payload = json.loads(snapshot.data_json or "{}")
        except json.JSONDecodeError:
            continue
        for item in payload.get("details") or []:
            name = (item.get("ReportNormName") or "").strip()
            term = (item.get("NormTerm") or "").strip()
            value = _safe_float(item.get("Value"))
            if not name or not term or value is None:
                continue
            series.setdefault(name, []).append(MetricPoint(term=term, value=value, unit=item.get("Unit")))

    for points in series.values():
        points.sort(key=lambda item: _term_rank(item.term))
    return series


def _load_company_profile(ticker: str) -> CompanyProfile:
    symbol = StockSymbol.objects.select_related("industry_group").filter(ticker__iexact=ticker).first()
    if not symbol:
        raise NotFoundError(f"Ticker not found: {ticker}")

    industry_name = symbol.industry_group.name if symbol.industry_group else None
    candidates = [
        _normalize_text(industry_name),
        _normalize_text(symbol.icb_name2),
    ]
    profile_type = "GENERAL"
    if any("ngan hang" in item for item in candidates if item):
        profile_type = "BANK"
    elif any(token in item for item in candidates if item for token in ("dich vu tai chinh", "chung khoan")):
        profile_type = "SECURITIES"

    return CompanyProfile(
        ticker=symbol.ticker,
        industry_group_name=industry_name,
        icb_name2=symbol.icb_name2,
        profile_type=profile_type,
    )


def _find_series(
    series_by_name: dict[str, list[MetricPoint]],
    *,
    includes: tuple[str, ...],
    excludes: tuple[str, ...] = (),
) -> list[MetricPoint]:
    for name, points in series_by_name.items():
        normalized = _normalize_text(name)
        if all(token in normalized for token in includes) and not any(token in normalized for token in excludes):
            return points
    return []


def _latest(points: list[MetricPoint]) -> MetricPoint | None:
    return points[-1] if points else None


def _previous(points: list[MetricPoint]) -> MetricPoint | None:
    return points[-2] if len(points) >= 2 else None


def _recent(points: list[MetricPoint], count: int = 4) -> list[MetricPoint]:
    return points[-count:] if points else []


def _format_value(value: float | None, unit: str | None = None, *, decimals: int = 1) -> str:
    if value is None:
        return "không đủ dữ liệu"
    if unit and "%" in unit:
        return f"{value:.{decimals}f}%"
    return f"{value:.{decimals}f}{(' ' + unit) if unit else ''}"


def _trend_word(value: float | None, *, positive_threshold: float = 0.0, negative_threshold: float = 0.0) -> str:
    if value is None:
        return "chưa rõ xu hướng"
    if value > positive_threshold:
        return "tích cực"
    if value < negative_threshold:
        return "suy yếu"
    return "đi ngang"


def _series_delta(points: list[MetricPoint], periods_back: int = 4) -> float | None:
    if len(points) < periods_back:
        return None
    start = points[-periods_back].value
    end = points[-1].value
    return end - start


def _series_direction(points: list[MetricPoint], *, periods: int = 4, positive_threshold: float = 5.0, negative_threshold: float = -5.0) -> str:
    delta = _series_delta(points, periods_back=periods)
    return _trend_word(delta, positive_threshold=positive_threshold, negative_threshold=negative_threshold)


def _positive_ratio(points: list[MetricPoint], count: int = 4) -> tuple[int, int]:
    recent = _recent(points, count)
    if not recent:
        return (0, 0)
    return (sum(1 for item in recent if item.value > 0), len(recent))


def _classification_label(profile_type: str) -> str:
    if profile_type == "BANK":
        return "Ngân hàng"
    if profile_type == "SECURITIES":
        return "Dịch vụ tài chính/chứng khoán"
    return "Doanh nghiệp"


def _score_to_rating(score: int) -> str:
    if score >= 3:
        return "Tích cực"
    if score <= -1:
        return "Thận trọng"
    return "Trung lập"


def build_overview_assessment(ticker: str) -> str:
    profile = _load_company_profile(ticker)
    series_by_name = _load_series_by_name(ticker)
    if not series_by_name:
        raise NotFoundError(f"No finance chart snapshots found for ticker {ticker}")

    revenue_growth = _find_series(series_by_name, includes=("tang truong", "doanh thu"))
    interest_income_growth = _find_series(series_by_name, includes=("tang truong", "thu nhap lai"))
    profit_growth = _find_series(series_by_name, includes=("tang truong", "loi nhuan"))
    net_margin = _find_series(series_by_name, includes=("ty suat sinh loi", "doanh thu thuan"))
    gross_margin = _find_series(series_by_name, includes=("loi nhuan gop bien",))
    cfo = _find_series(series_by_name, includes=("hoat dong kinh doanh",), excludes=("tai chinh", "dau tu"))
    cash_balance = _find_series(series_by_name, includes=("tuong duong tien",))
    roe = _find_series(series_by_name, includes=("roea",))
    roa = _find_series(series_by_name, includes=("roaa",))
    nim = _find_series(series_by_name, includes=("nim",))
    yoea = _find_series(series_by_name, includes=("yoea",))
    cof = _find_series(series_by_name, includes=("cof",))
    debt_ratio = _find_series(series_by_name, includes=("ty so no tren tong tai san",))
    debt_borrow_ratio = _find_series(series_by_name, includes=("ty so no vay tren tong tai san",))
    pe = _find_series(series_by_name, includes=("p/e",))
    pb = _find_series(series_by_name, includes=("p/b",))
    eps = _find_series(series_by_name, includes=("eps",))
    customer_deposit = _find_series(series_by_name, includes=("tien gui cua khach hang",))
    loan_book = _find_series(series_by_name, includes=("cho vay khach hang",))
    fvtpl_assets = _find_series(series_by_name, includes=("fvtpl",))
    brokerage_receivable = _find_series(series_by_name, includes=("phai thu cac dich vu ctck"))

    core_growth = interest_income_growth if profile.profile_type == "BANK" and interest_income_growth else revenue_growth
    rev_latest = _latest(core_growth)
    profit_latest = _latest(profit_growth)
    rev_prev = _previous(core_growth)
    profit_prev = _previous(profit_growth)
    margin_latest = _latest(net_margin) or _latest(gross_margin)
    margin_prev = _previous(net_margin) or _previous(gross_margin)
    cfo_latest = _latest(cfo)
    cash_latest = _latest(cash_balance)
    roe_latest = _latest(roe)
    roa_latest = _latest(roa)
    nim_latest = _latest(nim)
    nim_prev = _previous(nim)
    yoea_latest = _latest(yoea)
    cof_latest = _latest(cof)
    debt_latest = _latest(debt_ratio)
    debt_borrow_latest = _latest(debt_borrow_ratio)
    pe_latest = _latest(pe)
    pb_latest = _latest(pb)
    eps_latest = _latest(eps)
    customer_deposit_latest = _latest(customer_deposit)
    loan_book_latest = _latest(loan_book)
    fvtpl_latest = _latest(fvtpl_assets)
    brokerage_receivable_latest = _latest(brokerage_receivable)

    recent_cfo_points = cfo[-4:] if cfo else []
    positive_cfo_count = sum(1 for item in recent_cfo_points if item.value > 0)

    growth_trend = _trend_word(
        (rev_latest.value if rev_latest else 0) + (profit_latest.value if profit_latest else 0),
        positive_threshold=10,
        negative_threshold=-10,
    )
    margin_delta = None
    if margin_latest and margin_prev:
        margin_delta = margin_latest.value - margin_prev.value
    nim_delta = None
    if nim_latest and nim_prev:
        nim_delta = nim_latest.value - nim_prev.value

    revenue_direction = _series_direction(core_growth, positive_threshold=8, negative_threshold=-8)
    profit_direction = _series_direction(profit_growth, positive_threshold=8, negative_threshold=-8)
    margin_direction = _series_direction(net_margin or gross_margin, positive_threshold=0.5, negative_threshold=-0.5)
    cash_positive_ratio = _positive_ratio(cfo, 4)

    score = 0
    if rev_latest and rev_latest.value > 0:
        score += 1
    if profit_latest and profit_latest.value > 0:
        score += 1
    if roe_latest and roe_latest.value >= 12:
        score += 1
    if cfo_latest and cfo_latest.value > 0:
        score += 1
    if debt_latest and debt_latest.value >= 70:
        score -= 1
    if profit_latest and profit_latest.value < 0:
        score -= 2
    if roe_latest and roe_latest.value < 0:
        score -= 1
    if cfo_latest and cfo_latest.value < 0:
        score -= 1
    rating = _score_to_rating(score)

    valuation_parts: list[str] = []
    if pe_latest:
        if pe_latest.value <= 10:
            valuation_parts.append(f"P/E {pe_latest.value:.1f} lần, mức định giá thấp")
        elif pe_latest.value <= 18:
            valuation_parts.append(f"P/E {pe_latest.value:.1f} lần, mức định giá trung bình")
        else:
            valuation_parts.append(f"P/E {pe_latest.value:.1f} lần, mức định giá không còn rẻ")
    if pb_latest:
        if pb_latest.value <= 1:
            valuation_parts.append(f"P/B {pb_latest.value:.1f} lần, sát giá trị sổ sách")
        elif pb_latest.value <= 2:
            valuation_parts.append(f"P/B {pb_latest.value:.1f} lần, đang ở vùng trung bình")
        else:
            valuation_parts.append(f"P/B {pb_latest.value:.1f} lần, premium khá cao")

    lines: list[str] = []
    latest_term = rev_latest.term if rev_latest else profit_latest.term if profit_latest else margin_latest.term if margin_latest else None

    overview_label = "trung lập"
    if growth_trend == "tích cực":
        overview_label = "nghiêng về hướng tích cực"
    elif growth_trend == "suy yếu":
        overview_label = "có dấu hiệu suy yếu"
    lines.append(f"Xếp loại: {rating}.")
    lines.append(
        f"Tổng quan: dữ liệu cập nhật đến {latest_term or 'kỳ gần nhất'} cho thấy {ticker} thuộc nhóm {_classification_label(profile.profile_type).lower()}"
        + (f" trong ngành {profile.industry_group_name}" if profile.industry_group_name else "")
        + f", hiện đang ở trạng thái {overview_label}."
    )

    growth_parts: list[str] = []
    if rev_latest:
        lead_label = "thu nhập lãi thuần thay đổi" if profile.profile_type == "BANK" and interest_income_growth else "doanh thu thay đổi"
        growth_parts.append(f"{lead_label} {_format_value(rev_latest.value, rev_latest.unit or '%')}")
    if profit_latest:
        growth_parts.append(f"lợi nhuận thay đổi {_format_value(profit_latest.value, profit_latest.unit or '%')}")
    if rev_prev and profit_prev:
        growth_parts.append(
            f"so với kỳ trước, doanh thu {'cải thiện' if rev_latest and rev_latest.value > rev_prev.value else 'chậm lại'} "
            f"và lợi nhuận {'cải thiện' if profit_latest and profit_latest.value > profit_prev.value else 'chậm lại'}"
        )
    trend_bits: list[str] = []
    if revenue_direction != "chưa rõ xu hướng":
        metric_name = "thu nhập lõi" if profile.profile_type == "BANK" else "doanh thu"
        trend_bits.append(f"{metric_name} 4 kỳ gần nhất {revenue_direction}")
    if profit_direction != "chưa rõ xu hướng":
        trend_bits.append(f"lợi nhuận 4 kỳ gần nhất {profit_direction}")
    if trend_bits:
        growth_parts.append(", ".join(trend_bits))
    if growth_parts:
        lines.append("Tăng trưởng: " + "; ".join(growth_parts) + ".")

    efficiency_parts: list[str] = []
    if roe_latest:
        efficiency_parts.append(f"ROE năm gần nhất {_format_value(roe_latest.value, roe_latest.unit)}")
    if roa_latest:
        efficiency_parts.append(f"ROA {_format_value(roa_latest.value, roa_latest.unit)}")
    if profile.profile_type == "BANK":
        if nim_latest:
            efficiency_parts.append(f"NIM {_format_value(nim_latest.value, nim_latest.unit)}")
        if yoea_latest:
            efficiency_parts.append(f"YOEA {_format_value(yoea_latest.value, yoea_latest.unit)}")
        if cof_latest:
            efficiency_parts.append(f"COF {_format_value(cof_latest.value, cof_latest.unit)}")
    if efficiency_parts:
        margin_sentence = ""
        if profile.profile_type == "BANK" and nim_latest:
            margin_sentence = (
                f" Biên lãi thuần gần nhất ở mức {_format_value(nim_latest.value, nim_latest.unit)}"
                + (f", biến động {nim_delta:+.1f} điểm % so với kỳ trước." if nim_delta is not None else ".")
            )
        elif margin_latest:
            margin_sentence = (
                f" Biên lợi nhuận gần nhất đạt {_format_value(margin_latest.value, margin_latest.unit)}"
                + (
                    f", biến động {margin_delta:+.1f} điểm % so với kỳ trước."
                    if margin_delta is not None and margin_latest.unit and "%" in (margin_latest.unit or "")
                    else "."
                )
            )
        direction_text = ""
        if profile.profile_type != "BANK" and margin_direction != "chưa rõ xu hướng":
            direction_text = f" Xu hướng biên 4 kỳ gần nhất nhìn chung {margin_direction}."
        lines.append("Hiệu quả sinh lời: " + ", ".join(efficiency_parts) + "." + margin_sentence + direction_text)

    if profile.profile_type == "BANK":
        bank_balance_parts: list[str] = []
        if loan_book_latest:
            bank_balance_parts.append(f"cho vay khách hàng đạt {_format_value(loan_book_latest.value, loan_book_latest.unit)}")
        if customer_deposit_latest:
            bank_balance_parts.append(f"tiền gửi khách hàng ở mức {_format_value(customer_deposit_latest.value, customer_deposit_latest.unit)}")
        if bank_balance_parts:
            lines.append("Cân đối nguồn vốn: " + "; ".join(bank_balance_parts) + ".")
    elif profile.profile_type == "SECURITIES":
        sec_parts: list[str] = []
        if fvtpl_latest:
            sec_parts.append(f"quy mô FVTPL ở mức {_format_value(fvtpl_latest.value, fvtpl_latest.unit)}")
        if brokerage_receivable_latest:
            sec_parts.append(f"phải thu dịch vụ chứng khoán {_format_value(brokerage_receivable_latest.value, brokerage_receivable_latest.unit)}")
        if cash_latest:
            sec_parts.append(f"tiền và tương đương tiền cuối kỳ {_format_value(cash_latest.value, cash_latest.unit)}")
        if sec_parts:
            lines.append("Chất lượng tài sản tài chính: " + "; ".join(sec_parts) + ".")
    elif cfo_latest or cash_latest:
        cfo_view = "dòng tiền kinh doanh chưa rõ xu hướng"
        if cfo_latest:
            if cfo_latest.value > 0:
                cfo_view = f"dòng tiền kinh doanh dương {_format_value(cfo_latest.value, cfo_latest.unit)}"
            else:
                cfo_view = f"dòng tiền kinh doanh âm {_format_value(abs(cfo_latest.value), cfo_latest.unit)}"
        stability = f"; {positive_cfo_count}/{len(recent_cfo_points)} quý gần nhất có dòng tiền kinh doanh dương" if recent_cfo_points else ""
        cash_view = f"; tiền và tương đương tiền cuối kỳ {_format_value(cash_latest.value, cash_latest.unit)}" if cash_latest else ""
        lines.append("Dòng tiền: " + cfo_view + stability + cash_view + ".")

    risk_parts: list[str] = []
    if debt_latest and profile.profile_type != "BANK":
        risk_parts.append(f"tỷ số nợ/tổng tài sản {_format_value(debt_latest.value, debt_latest.unit)}")
    if debt_borrow_latest and profile.profile_type != "BANK":
        risk_parts.append(f"tỷ số nợ vay/tổng tài sản {_format_value(debt_borrow_latest.value, debt_borrow_latest.unit)}")
    if roe_latest and roe_latest.value < 0:
        risk_parts.append("ROE âm cho thấy hiệu quả sử dụng vốn đang yếu")
    if cfo_latest and cfo_latest.value < 0 and profile.profile_type == "GENERAL":
        risk_parts.append("dòng tiền kinh doanh âm cần được theo dõi")
    if profile.profile_type == "BANK" and nim_latest and nim_latest.value < 3:
        risk_parts.append("NIM ở vùng thấp, phản ánh áp lực lên chênh lệch lãi suất")
    if profile.profile_type == "SECURITIES" and fvtpl_latest:
        risk_parts.append("kết quả kinh doanh có thể biến động theo diễn biến thị trường và danh mục tự doanh")
    if risk_parts:
        lines.append("Rủi ro tài chính: " + "; ".join(risk_parts) + ".")

    if eps_latest:
        potential_note = "EPS dương, cho thấy khả năng tạo lợi nhuận cho cổ đông" if eps_latest.value > 0 else "EPS âm, cần thận trọng với khả năng tạo giá trị ngắn hạn"
        lines.append(f"Chỉ số cổ đông: EPS 4 quý gần nhất {_format_value(eps_latest.value, eps_latest.unit)}; {potential_note}.")

    if valuation_parts:
        lines.append("Định giá: " + "; ".join(valuation_parts) + ".")

    potential_parts: list[str] = []
    if rev_latest and rev_latest.value > 10:
        potential_parts.append("dư địa tăng trưởng doanh thu vẫn còn")
    if profit_latest and profit_latest.value > 10:
        potential_parts.append("động lực lợi nhuận đang mở rộng")
    if cfo_latest and cfo_latest.value > 0 and profile.profile_type == "GENERAL":
        potential_parts.append("chất lượng lợi nhuận được hỗ trợ bởi dòng tiền")
    if roe_latest and roe_latest.value >= 15:
        potential_parts.append("hiệu quả sử dụng vốn ở mức khá")
    if profile.profile_type == "BANK" and nim_latest and nim_latest.value >= 4:
        potential_parts.append("biên lãi thuần đủ rộng để hỗ trợ tăng trưởng lợi nhuận")
    if profile.profile_type == "SECURITIES" and fvtpl_latest and profit_latest and profit_latest.value > 0:
        potential_parts.append("có khả năng hưởng lợi khi thanh khoản thị trường duy trì tích cực")
    if potential_parts:
        lines.append("Tiềm năng: " + "; ".join(potential_parts) + ".")

    lines.append(
        "Lưu ý: nhận định tổng quan này được tổng hợp từ các báo cáo tài chính công khai của doanh nghiệp, phù hợp để tham khảo nhanh; khi ra quyết định vẫn cần đối chiếu thêm bối cảnh ngành, chất lượng tài sản và kế hoạch kinh doanh."
    )
    return "\n".join(lines)


@transaction.atomic
def upsert_generated_assessment(ticker: str) -> dict:
    t = (ticker or "").strip().upper()
    if not t:
        raise BadRequestError("Ticker is required")

    sym = StockSymbol.objects.filter(ticker__iexact=t).first()
    if not sym:
        raise NotFoundError("Ticker not found")

    has_quarter = StockFinanceChartSnapshot.objects.filter(ticker__iexact=t, report_type="QUARTER").exists()
    has_year = StockFinanceChartSnapshot.objects.filter(ticker__iexact=t, report_type="YEAR").exists()
    if not has_quarter or not has_year:
        raise BadRequestError("Ticker must have both QUARTER and YEAR finance chart data")

    overview = build_overview_assessment(t)
    latest_ts = StockFinanceChartSnapshot.objects.filter(ticker__iexact=t).aggregate(m=Max("updated_at"))["m"]
    now = timezone.now()
    obj, created = StockFinanceChartAssessment.objects.get_or_create(
        stock_symbol=sym,
        defaults={
            "ticker": t,
            "overview_assessment": overview,
            "assessment_status": "GENERATED",
            "source_synced_at": latest_ts,
            "created_at": now,
            "updated_at": now,
        },
    )
    if not created:
        obj.ticker = t
        obj.overview_assessment = overview
        obj.assessment_status = "GENERATED"
        obj.source_synced_at = latest_ts
        obj.updated_at = now
        obj.save(update_fields=["ticker", "overview_assessment", "assessment_status", "source_synced_at", "updated_at"])

    return {
        "stockSymbolId": sym.id,
        "ticker": t,
        "overviewAssessment": obj.overview_assessment,
        "assessmentStatus": obj.assessment_status,
        "sourceSyncedAt": obj.source_synced_at.isoformat() if obj.source_synced_at else None,
        "updatedAt": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def backfill_generated_assessments(limit: int | None = None) -> dict:
    tickers = (
        StockFinanceChartSnapshot.objects.values_list("ticker", flat=True)
        .distinct()
        .order_by("ticker")
    )
    eligible: list[str] = []
    for ticker in tickers:
        ticker_u = str(ticker).upper()
        report_types = set(
            StockFinanceChartSnapshot.objects.filter(ticker__iexact=ticker_u)
            .values_list("report_type", flat=True)
            .distinct()
        )
        if {"QUARTER", "YEAR"}.issubset(report_types):
            eligible.append(ticker_u)
    if limit is not None:
        eligible = eligible[:limit]

    generated = 0
    failed: list[dict] = []
    for ticker in eligible:
        try:
            upsert_generated_assessment(ticker)
            generated += 1
        except Exception as exc:
            failed.append({"ticker": ticker, "error": str(exc)})

    return {
        "eligibleCount": len(eligible),
        "generatedCount": generated,
        "failedCount": len(failed),
        "failed": failed[:20],
    }
