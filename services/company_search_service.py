# -*- coding: utf-8 -*-
"""Company ledger deep-search utilities shared by local and REST data paths.

The Android UI needs to find companies through the text stored inside their
ledger entries, not only by company name.  Keep the matching pure-Python so it
works consistently on Android SQLite, Windows SQLite, and REST payloads.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_WHITESPACE_RE = re.compile(r"\s+")

_DIGIT_MAP = str.maketrans({
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
})

_ARABIC_CHAR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي",
    "ؤ": "و",
    "ة": "ه",
    "ـ": "",
})

FIELD_LABELS = {
    "company_name": "اسم الشركة",
    "notes": "ملاحظة قيد",
    "payment_reminder_note": "ملاحظة تنبيه الدفع",
    "source_ref": "رقم المرجع",
    "counterparty_company_name": "الطرف المقابل",
    "date": "التاريخ",
    "amount_original": "المبلغ الأصلي",
    "currency_original": "العملة الأصلية",
    "created_username": "المستخدم",
    "created_full_name": "اسم المستخدم",
    "status": "الحالة",
    "type": "نوع القيد",
}

SEARCH_FIELDS = (
    "company_name",
    "notes",
    "payment_reminder_note",
    "source_ref",
    "counterparty_company_name",
    "date",
    "amount_original",
    "currency_original",
    "created_username",
    "created_full_name",
    "status",
    "type",
)


def normalize_search_text(value: Any) -> str:
    """Return a search-friendly string.

    Arabic variants are intentionally folded so searching for "احمد" can find
    "أحمد", and "شركه" can find "شركة".  Western/Arabic/Persian digits are
    normalized as well because mobile users often mix numeric keyboards.
    """
    if value is None:
        return ""
    text = str(value).strip().lower().translate(_DIGIT_MAP)
    text = _ARABIC_DIACRITICS_RE.sub("", text)
    text = text.translate(_ARABIC_CHAR_MAP)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _tokens(query: str) -> List[str]:
    return [p for p in normalize_search_text(query).split(" ") if p]


def _matches(norm_haystack: str, query_tokens: List[str]) -> bool:
    if not query_tokens:
        return False
    return all(token in norm_haystack for token in query_tokens)


def make_snippet(value: Any, query: str, max_len: int = 90) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= max_len:
        return text
    norm_text = normalize_search_text(text)
    tokens = _tokens(query)
    pos = -1
    for token in tokens:
        pos = norm_text.find(token)
        if pos >= 0:
            break
    if pos < 0:
        return text[: max_len - 1].rstrip() + "…"
    # Approximate position; normalization can change length, but this is close
    # enough for a compact mobile preview.
    start = max(0, pos - max_len // 3)
    end = min(len(text), start + max_len)
    if end - start < max_len:
        start = max(0, end - max_len)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def enrich_expense_match(row: Dict[str, Any], query: str) -> Dict[str, Any] | None:
    qtokens = _tokens(query)
    if not qtokens:
        return None
    first_field = None
    first_value = None
    matched_fields: List[str] = []
    for field in SEARCH_FIELDS:
        value = row.get(field)
        if value is None:
            continue
        if _matches(normalize_search_text(value), qtokens):
            matched_fields.append(field)
            if first_field is None:
                first_field = field
                first_value = value
    if not matched_fields:
        return None
    out = dict(row)
    out["result_type"] = "ledger_entry"
    out["entry_id"] = row.get("id")
    out["matched_fields"] = matched_fields
    out["matched_field"] = first_field
    out["matched_label"] = FIELD_LABELS.get(first_field or "", first_field or "")
    out["snippet"] = make_snippet(first_value, query) if first_value is not None else ""
    # Company name hits are useful but lower-priority than a note/reference hit.
    out["score"] = 80 if first_field != "company_name" else 50
    return out


def search_expense_rows(rows: Iterable[Dict[str, Any]], query: str, limit: int = 100) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        match = enrich_expense_match(dict(row), query)
        if not match:
            continue
        key = (match.get("entry_id"), match.get("company_name"), tuple(match.get("matched_fields") or []))
        if key in seen:
            continue
        seen.add(key)
        results.append(match)
    results.sort(key=lambda r: (int(r.get("score") or 0), str(r.get("date") or ""), int(r.get("entry_id") or 0)), reverse=True)
    return results[: max(1, int(limit or 100))]
