# -*- coding: utf-8 -*-
"""PNG image export for statements and reporting-center results.

The HTML/CSV exporters remain the source for printing and analysis.  This
module renders a mobile-friendly PNG that can be shared directly through
WhatsApp or the Android share sheet without depending on a browser.
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Dict, Iterable, List

from config import get_company_info
from currency import currency
from reports.account_statement import (
    LAYOUT_COMPACT,
    build_reconciliation_rows,
    build_rows,
)
from services.file_export_service import FileExportService

try:  # Pillow is intentionally optional at import time; buttons surface errors.
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except Exception:  # pragma: no cover - exercised only on runtimes missing Pillow
    Image = ImageDraw = ImageFont = ImageOps = None

PRIMARY = "#0A3F70"
PRIMARY_SOFT = "#EAF4FF"
TEXT = "#172033"
MUTED = "#667085"
BORDER = "#D8E4EE"
SUCCESS = "#1FA56A"
DANGER = "#E54848"
WARNING = "#D9A441"
BG = "#F7FAFC"
WHITE = "#FFFFFF"
CARD_BG = "#F9FBFD"
PAGE_W = 1240
MARGIN = 64


def _require_pillow() -> None:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("تصدير PNG يحتاج مكتبة Pillow. أعد بناء APK بعد تثبيت اعتماد Pillow.")


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name or "report")).strip("._ ") or "report"


def _report_path(filename: str) -> str:
    return FileExportService.build_path(_safe_filename(filename), "reports", temporary=True)


def _font_candidates() -> List[str]:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [
        os.path.join(root, "assets", "fonts", "Tajawal-Regular.ttf"),
        os.path.join(root, "assets", "fonts", "NotoNaskhArabic-Regular.ttf"),
        "/system/fonts/NotoNaskhArabic-Regular.ttf",
        "/system/fonts/NotoSansArabic-Regular.ttf",
        "/system/fonts/DroidSansArabic.ttf",
        "/system/fonts/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]


def _load_font(size: int, *, bold: bool = False):
    _require_pillow()
    candidates = _font_candidates()
    if bold:
        candidates = [c.replace("Regular", "Bold").replace(".ttf", "-Bold.ttf") for c in candidates] + candidates
    for path in candidates:
        try:
            if path and os.path.exists(path):
                return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


_FONT_CACHE: Dict[tuple[int, bool], object] = {}


def _font(size: int, *, bold: bool = False):
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = _load_font(size, bold=bold)
    return _FONT_CACHE[key]


def _txt_size(draw, text: str, font) -> tuple[int, int]:
    if not text:
        return 0, 0
    try:
        box = draw.textbbox((0, 0), str(text), font=font, direction="rtl")
    except Exception:
        box = draw.textbbox((0, 0), str(text), font=font)
    return max(0, box[2] - box[0]), max(0, box[3] - box[1])


def _draw_text(draw, xy, text: object, font, fill=TEXT, *, anchor: str = "ra", rtl: bool = True) -> None:
    kwargs = {"font": font, "fill": fill, "anchor": anchor}
    if rtl:
        kwargs["direction"] = "rtl"
    try:
        draw.text(xy, "" if text is None else str(text), **kwargs)
    except Exception:
        # Several Android Pillow builds ship without libraqm or with a default
        # bitmap font that rejects the ``direction`` keyword.  PNG export must
        # never look like a dead button because text shaping failed.  Retry with
        # plain drawing; the report remains usable and the UI can still share it.
        kwargs.pop("direction", None)
        try:
            draw.text(xy, "" if text is None else str(text), **kwargs)
        except Exception:
            # Last resort: avoid aborting the entire image because of one label.
            pass


def _wrap_text(draw, text: object, font, max_width: int, *, rtl: bool = True, max_lines: int | None = None) -> List[str]:
    text = str(text or "").replace("\n", " ").strip()
    if not text:
        return [""]
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _txt_size(draw, candidate, font)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if max_lines and len(lines) >= max_lines:
                break
    if current and (not max_lines or len(lines) < max_lines):
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    if max_lines and lines and len(words) > sum(len(x.split()) for x in lines):
        lines[-1] = (lines[-1].rstrip("…") + "…")
    return lines or [""]


def _rounded_rect(draw, box, radius=24, fill=WHITE, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _money_color(value: str, default=PRIMARY) -> str:
    text = str(value or "")
    if "-" in text:
        return DANGER
    return default


def _make_canvas(height: int):
    _require_pillow()
    return Image.new("RGB", (PAGE_W, max(900, int(height))), BG)


def _draw_brand_header(draw, y: int, *, title: str, subtitle: str, account: str | None = None) -> int:
    info = get_company_info()
    right = PAGE_W - MARGIN
    left = MARGIN
    _rounded_rect(draw, (left, y, PAGE_W - MARGIN, y + 160), radius=34, fill=WHITE, outline=BORDER, width=2)
    _draw_text(draw, (right - 28, y + 46), str(info.get("name") or "هوى الشام للسياحة والسفر"), _font(34, bold=True), PRIMARY)
    _draw_text(draw, (right - 28, y + 94), title, _font(26, bold=True), TEXT)
    _draw_text(draw, (right - 28, y + 132), subtitle, _font(20), MUTED)
    if account:
        _rounded_rect(draw, (left + 24, y + 40, left + 360, y + 112), radius=24, fill=PRIMARY_SOFT, outline=None)
        _draw_text(draw, (left + 336, y + 84), account, _font(22, bold=True), PRIMARY)
    return y + 190


def _draw_summary(draw, y: int, items: List[Dict[str, str]]) -> int:
    if not items:
        return y
    gap = 16
    count = min(4, len(items))
    w = (PAGE_W - (2 * MARGIN) - (gap * (count - 1))) // count
    x = PAGE_W - MARGIN - w
    for item in items[:count]:
        _rounded_rect(draw, (x, y, x + w, y + 112), radius=26, fill=WHITE, outline=BORDER, width=2)
        _draw_text(draw, (x + w - 24, y + 38), item.get("label", ""), _font(18), MUTED)
        cls = str(item.get("class") or "balance")
        color = SUCCESS if cls == "debit" else DANGER if cls == "credit" else _money_color(str(item.get("value") or ""), PRIMARY)
        _draw_text(draw, (x + w - 24, y + 82), item.get("value", ""), _font(24, bold=True), color)
        x -= w + gap
    return y + 138


def _draw_table_header(draw, y: int, columns: List[str], widths: List[int]) -> int:
    x = PAGE_W - MARGIN
    h = 58
    for label, w in zip(columns, widths):
        x2 = x - w
        draw.rectangle((x2, y, x, y + h), fill=PRIMARY, outline=PRIMARY)
        _draw_text(draw, (x - 14, y + 38), label, _font(18, bold=True), WHITE)
        x = x2
    return y + h


def _draw_statement_rows(draw, y: int, rows: List[Dict[str, str]], *, max_rows: int = 60) -> int:
    columns = ["التاريخ", "البيان", "لنا", "له", "الرصيد"]
    widths = [150, 430, 180, 180, 172]
    y = _draw_table_header(draw, y, columns, widths)
    row_font = _font(18)
    small_font = _font(15)
    clipped = len(rows) > max_rows
    for idx, row in enumerate(rows[:max_rows]):
        desc = row.get("notes", "")
        details = []
        if row.get("reference"):
            details.append(f"المرجع: {row.get('reference')}")
        if row.get("person_name"):
            details.append(f"الزبون: {row.get('person_name')}")
        if row.get("service_type"):
            details.append(f"الخدمة: {row.get('service_type')}")
        detail_text = " | ".join(details)
        desc_lines = _wrap_text(draw, desc, row_font, 405, max_lines=2)
        detail_lines = _wrap_text(draw, detail_text, small_font, 405, max_lines=2) if detail_text else []
        row_h = max(76, 34 * len(desc_lines) + 26 * len(detail_lines) + 26)
        fill = WHITE if idx % 2 == 0 else CARD_BG
        x = PAGE_W - MARGIN
        values = [row.get("date", ""), "\n".join(desc_lines), row.get("debit", ""), row.get("credit", ""), row.get("running_balance", "")]
        for col_idx, (value, w) in enumerate(zip(values, widths)):
            x2 = x - w
            draw.rectangle((x2, y, x, y + row_h), fill=fill, outline=BORDER)
            if col_idx == 1:
                ty = y + 30
                for line in desc_lines:
                    _draw_text(draw, (x - 14, ty), line, row_font, TEXT)
                    ty += 30
                for line in detail_lines:
                    _draw_text(draw, (x - 14, ty), line, small_font, MUTED)
                    ty += 24
            else:
                color = SUCCESS if col_idx == 2 and value else DANGER if col_idx == 3 and value else _money_color(str(value), PRIMARY if col_idx == 4 else TEXT)
                _draw_text(draw, (x - 12, y + 45), value or "—", row_font, color)
            x = x2
        y += row_h
    if not rows:
        _rounded_rect(draw, (MARGIN, y, PAGE_W - MARGIN, y + 120), radius=20, fill=WHITE, outline=BORDER)
        _draw_text(draw, (PAGE_W - MARGIN - 28, y + 70), "لا توجد قيود ضمن الكشف", _font(22), MUTED)
        y += 130
    if clipped:
        _rounded_rect(draw, (MARGIN, y + 14, PAGE_W - MARGIN, y + 88), radius=20, fill="#FFF7E3", outline=None)
        _draw_text(draw, (PAGE_W - MARGIN - 24, y + 60), f"تم عرض أول {max_rows} قيد في الصورة. HTML وCSV يحتويان كل القيود.", _font(18), WARNING)
        y += 104
    return y


def export_statement_image(company_name: str, records: Iterable[Dict], output_path: str | None = None, *, reconciliation: bool = True, max_rows: int = 60) -> str:
    """Export an account/reconciliation statement as a PNG image."""
    _require_pillow()
    display_currency = currency.get_display_currency()
    rows, totals = (build_reconciliation_rows(records, display_currency) if reconciliation else build_rows(records, display_currency))
    title = "كشف حساب للمطابقة" if reconciliation else "كشف حساب شركة"
    generated = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_debit = currency.format_amount_full(currency.convert(float(totals.get("total_debit_usd") or 0), "USD", display_currency), display_currency)
    total_credit = currency.format_amount_full(currency.convert(float(totals.get("total_credit_usd") or 0), "USD", display_currency), display_currency)
    balance_value = float(totals.get("balance_usd") or 0)
    balance = currency.format_amount_full(currency.convert(balance_value, "USD", display_currency), display_currency)
    # PNG is for quick mobile sharing, not an archival full ledger.  Old phones
    # can silently kill the Python runtime on very tall bitmaps, making the
    # button appear unresponsive.  Keep the image compact and point users to
    # HTML/CSV for the full report.
    display_rows = rows[:max_rows]
    approx_height = 560 + max(1, len(display_rows)) * 118 + (120 if len(rows) > max_rows else 0)
    img = _make_canvas(min(max(approx_height, 1100), 9000))
    draw = ImageDraw.Draw(img)
    y = 44
    subtitle = f"العملة: {display_currency} · تاريخ الإنشاء: {generated}"
    y = _draw_brand_header(draw, y, title=title, subtitle=subtitle, account=company_name)
    y = _draw_summary(draw, y, [
        {"label": "لنا", "value": total_debit, "class": "debit"},
        {"label": "له", "value": total_credit, "class": "credit"},
        {"label": "الصافي", "value": balance, "class": "balance"},
    ])
    if reconciliation:
        _rounded_rect(draw, (MARGIN, y, PAGE_W - MARGIN, y + 74), radius=22, fill=PRIMARY_SOFT, outline=BORDER)
        note = "هذا الكشف مخصص للمطابقة ولا يُعد مخالصة نهائية إلا بعد التأكيد."
        _draw_text(draw, (PAGE_W - MARGIN - 22, y + 45), note, _font(18), PRIMARY)
        y += 94
    y = _draw_statement_rows(draw, y, rows, max_rows=max_rows)
    footer = "تم إنشاء الصورة بواسطة نظام هوى الشام"
    _draw_text(draw, (PAGE_W - MARGIN, y + 50), footer, _font(16), MUTED)
    final_h = min(y + 90, img.height)
    img = img.crop((0, 0, PAGE_W, final_h))
    if ImageOps is not None:
        img = ImageOps.expand(img, border=0, fill=BG)
    filename = f"{'reconciliation' if reconciliation else 'statement'}_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    output_path = output_path or _report_path(filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # ``optimize=True`` is CPU-heavy on Android and can make export feel dead.
    img.save(output_path, format="PNG", optimize=False, compress_level=3)
    return output_path


def _report_summary_items(report) -> List[Dict[str, str]]:
    items = []
    for item in list(getattr(report, "summary", []) or [])[:4]:
        items.append({
            "label": str(item.get("label") or ""),
            "value": str(item.get("value") or ""),
            "class": str(item.get("class") or "balance"),
        })
    return items


def _draw_report_rows(draw, y: int, report, *, max_rows: int = 180) -> int:
    columns = list(getattr(report, "columns", []) or [])[:7]
    if not columns:
        return y
    # Give the first textual column more width, keep financial columns readable.
    first_w = 270
    other_w = (PAGE_W - (2 * MARGIN) - first_w) // max(1, len(columns) - 1) if len(columns) > 1 else PAGE_W - 2 * MARGIN
    widths = [first_w] + [other_w] * (len(columns) - 1)
    labels = [str(c.get("label") or c.get("key") or "") for c in columns]
    y = _draw_table_header(draw, y, labels, widths)
    row_font = _font(17)
    rows = list(getattr(report, "rows", []) or [])
    clipped = len(rows) > max_rows
    for idx, row in enumerate(rows[:max_rows]):
        row_h = 78
        fill = WHITE if idx % 2 == 0 else CARD_BG
        x = PAGE_W - MARGIN
        for c, w in zip(columns, widths):
            key = str(c.get("key") or "")
            value = str(row.get(key, "") or "")
            lines = _wrap_text(draw, value, row_font, w - 22, max_lines=2)
            x2 = x - w
            draw.rectangle((x2, y, x, y + row_h), fill=fill, outline=BORDER)
            color = _money_color(value, TEXT)
            ty = y + 31
            for line in lines:
                _draw_text(draw, (x - 12, ty), line, row_font, color)
                ty += 27
            x = x2
        y += row_h
    if not rows:
        _rounded_rect(draw, (MARGIN, y, PAGE_W - MARGIN, y + 120), radius=20, fill=WHITE, outline=BORDER)
        _draw_text(draw, (PAGE_W - MARGIN - 28, y + 70), "لا توجد بيانات ضمن الفلاتر المحددة", _font(22), MUTED)
        y += 130
    if clipped:
        _rounded_rect(draw, (MARGIN, y + 14, PAGE_W - MARGIN, y + 88), radius=20, fill="#FFF7E3", outline=None)
        _draw_text(draw, (PAGE_W - MARGIN - 24, y + 60), f"تم عرض أول {max_rows} صف في الصورة. HTML وCSV يحتويان كل الصفوف.", _font(18), WARNING)
        y += 104
    return y


def export_report_image(report, output_path: str | None = None, *, max_rows: int = 40) -> str:
    """Export a ReportingCenterService result as a PNG image."""
    _require_pillow()
    rows = list(getattr(report, "rows", []) or [])
    approx_height = 560 + max(1, min(len(rows), max_rows)) * 86 + (140 if len(rows) > max_rows else 0)
    img = _make_canvas(min(max(approx_height, 1100), 9000))
    draw = ImageDraw.Draw(img)
    y = 44
    subtitle = f"{getattr(report, 'period_label', '')} · العملة: {getattr(report, 'display_currency', '')} · {getattr(report, 'generated_at', '')}"
    y = _draw_brand_header(draw, y, title=str(getattr(report, "title", "تقرير")), subtitle=subtitle, account=str(getattr(report, "category", "التقارير")))
    y = _draw_summary(draw, y, _report_summary_items(report))
    _rounded_rect(draw, (MARGIN, y, PAGE_W - MARGIN, y + 74), radius=22, fill=PRIMARY_SOFT, outline=BORDER)
    _draw_text(draw, (PAGE_W - MARGIN - 22, y + 45), "صورة تقرير قابلة للمشاركة. HTML وCSV متاحان للتفاصيل الكاملة.", _font(18), PRIMARY)
    y += 94
    y = _draw_report_rows(draw, y, report, max_rows=max_rows)
    _draw_text(draw, (PAGE_W - MARGIN, y + 50), "تم إنشاء الصورة بواسطة نظام هوى الشام", _font(16), MUTED)
    img = img.crop((0, 0, PAGE_W, min(y + 90, img.height)))
    filename = f"{getattr(report, 'filename_slug', 'report')}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    output_path = output_path or _report_path(filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # ``optimize=True`` is CPU-heavy on Android and can make export feel dead.
    img.save(output_path, format="PNG", optimize=False, compress_level=3)
    return output_path
