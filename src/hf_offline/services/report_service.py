"""Print-ready, modern RTL reports (HTML) generated on demand.

Design language (the "طباعة عصرية" upgrade over the reference app):

* one gradient brand band (indigo → cyan) instead of a flat blue header
* device identifiers (IMEI / S/N) in a monospace, LTR-safe style so long
  digit strings never reflow under RTL reordering
* per-category result tables with colored status dots + soft tint rows
* a single self-contained <style> block — no external assets, so the file
  is safe to open offline, print from the browser, or share as-is
* @media print rules: shadows off, exact colors, page-break protection
"""

from __future__ import annotations

import datetime
import json
from html import escape
from typing import Any, Mapping

from hf_offline.core.database import Database
from hf_offline.services.device_service import DeviceService
from hf_offline.services.diagnosis_service import DiagnosisService

ACCENTS: dict[str, tuple[str, str]] = {
    "default": ("#4F46E5", "#06B6D4"),
    "teal": ("#0F766E", "#0EA5E9"),
    "blue": ("#1D4ED8", "#06B6D4"),
    "violet": ("#6D28D9", "#7C3AED"),
    "orange": ("#EA580C", "#F59E0B"),
}

_RESULT_STYLE = {
    "passed": ("ناجح", "#16A34A", "#ECFDF5"),
    "failed": ("فاشل", "#DC2626", "#FEF2F2"),
    "warning": ("تحذير", "#B45309", "#FFFBEB"),
    "na": ("غير مُفعّل", "#64748B", "#F1F5F9"),
}

_DEVICE_STATUS_LABEL = {
    "in_queue": "قيد الانتظار",
    "in_repair": "قيد الإصلاح",
    "diagnosing": "قيد الفحص",
    "done": "مكتمل",
}


class ReportService:
    def __init__(self, db: Database, devices: DeviceService, diagnoses: DiagnosisService):
        self.db = db
        self.devices = devices
        self.diagnoses = diagnoses

    # ---- data ------------------------------------------------------------

    def build_report(self, diagnosis_id: int) -> dict[str, Any] | None:
        """Assemble everything a printed report needs (or None if the
        diagnosis doesn't exist / has no device)."""
        diag = self.diagnoses.get(diagnosis_id)
        if not diag:
            return None
        device_id = int(diag["device_id"])
        device = self.devices.get(device_id)
        if not device:
            return None
        groups = self.diagnoses.group_by_category(diagnosis_id)
        return {
            "diagnosis": diag,
            "device": device,
            "groups": groups,
            "result": diag.get("result") or "incomplete",
        }

    # ---- rendering -------------------------------------------------------

    @staticmethod
    def _e(value: Any) -> str:
        return escape(str(value or ""), quote=True)

    @staticmethod
    def _now_str() -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _device_label(device: Mapping) -> str:
        brand = str(device.get("brand") or "").strip() or "علامة غير محددة"
        model = str(device.get("model") or "").strip()
        return f"{brand} {model}".strip() or "جهاز"

    def report_html(self, diagnosis_id: int, *, accent: str = "default", settings: dict[str, str] | None = None) -> str:
        """Render the full self-contained HTML document for one diagnosis."""
        data = self.build_report(diagnosis_id)
        if data is None:
            raise ValueError(f"no report for diagnosis {diagnosis_id}")
        settings = settings or {}
        accent_c1, accent_c2 = ACCENTS.get(accent, ACCENTS["default"])
        device = data["device"]
        diag = data["diagnosis"]
        result = str(data["result"])
        result_label, result_fg, result_bg = {
            "passed": ("كل الفحوصات ناجحة", "#15803D", "#ECFDF5"),
            "failed": ("توجد فحوصات فاشلة", "#B91C1C", "#FEF2F2"),
        }.get(result, ("جلسة غير مكتملة", "#B45309", "#FFFBEB"))

        shop = settings.get("shop_name") or "ورشة إتش-إف"
        tech = settings.get("technician_name") or "المهندس"

        customer_bits = " · ".join(
            p for p in (
                str(device.get("customer_name") or "").strip(),
                str(device.get("customer_phone") or "").strip(),
            ) if p
        )

        imei = str(device.get("imei") or "").strip()
        imei2 = str(device.get("imei2") or "").strip()
        serial = str(device.get("serial") or "").strip()

        spec_rows: list[tuple[str, str]] = []
        if serial:
            spec_rows.append(("S/N", serial))
        if imei:
            spec_rows.append(("IMEI", imei))
        if imei2:
            spec_rows.append(("IMEI 2", imei2))
        if str(device.get("color") or "").strip():
            spec_rows.append(("اللون", str(device["color"]).strip()))
        if str(device.get("os_version") or "").strip():
            spec_rows.append(("نظام التشغيل", str(device["os_version"]).strip()))
        spec_html = "".join(
            f'<div class="spec"><span class="spec-k">{self._e(k)}</span><span class="spec-v mono">{self._e(v)}</span></div>'
            for k, v in spec_rows
        )

        section_html_parts: list[str] = []
        for group in data["groups"]:
            rows: list[str] = []
            for item in group["items"]:
                label, fg, bg = _RESULT_STYLE.get(str(item["status"]), _RESULT_STYLE["na"])
                detail = str(item.get("detail") or "").strip()
                rows.append(
                    f'<tr><td class="t-name">{self._e(item["test_name"])}</td>'
                    f'<td class="t-detail">{self._e(detail) or "—"}</td>'
                    f'<td class="t-status"><span class="dot" style="background:{fg}"></span>'
                    f'<span class="pill" style="color:{fg};background:{bg}">{label}</span></td></tr>'
                )
            section_html_parts.append(
                f'<section class="card">'
                f'<h2>{self._e(group["category"])}</h2>'
                f'<table><thead><tr><th>الفحص</th><th>التفاصيل</th><th>النتيجة</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></section>'
            )

        notes = str(device.get("notes") or "").strip()
        notes_html = f'<section class="card notes"><h2>ملاحظات الورشة</h2><p>{self._e(notes) or "—"}</p></section>' if notes else ""

        return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>تقرير فحص — {self._e(self._device_label(device))}</title>
<style>
  :root {{ --c1:{accent_c1}; --c2:{accent_c2}; }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:#F1F5F9; color:#0F172A;
    font-family:"Segoe UI","Noto Sans Arabic","Helvetica Neue",Arial,sans-serif;
    font-size:14px; line-height:1.7;
  }}
  .page {{ max-width:820px; margin:0 auto; padding:24px 16px 40px; }}
  .brand {{
    background:linear-gradient(120deg,var(--c1),var(--c2));
    color:#fff; border-radius:18px 18px 0 0; padding:20px 22px;
    display:flex; justify-content:space-between; align-items:center; gap:12px;
  }}
  .brand h1 {{ margin:0; font-size:19px; font-weight:800; }}
  .brand .sub {{ font-size:12px; opacity:.85; margin-top:2px; }}
  .brand .logo {{
    width:46px; height:46px; border-radius:14px; background:rgba(255,255,255,.18);
    display:flex; align-items:center; justify-content:center; font-weight:800; font-size:17px;
    letter-spacing:1px;
  }}
  .result {{
    margin:14px 0 0; padding:14px 18px; border-radius:14px;
    display:flex; justify-content:space-between; align-items:center; gap:10px;
    color:{result_fg}; background:{result_bg}; font-weight:700; font-size:14px;
  }}
  .result .meta {{ font-weight:500; font-size:12px; opacity:.85; }}
  .card {{ background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:16px 18px; margin-top:14px; }}
  .card h2 {{ margin:0 0 10px; font-size:14px; font-weight:800; color:#111827; }}
  .device {{ display:flex; justify-content:space-between; gap:14px; flex-wrap:wrap; }}
  .device .name {{ font-size:16px; font-weight:800; }}
  .device .status-chip {{
    display:inline-block; margin-top:6px; padding:3px 10px; border-radius:10px;
    font-size:11px; font-weight:700; background:#EEF2FF; color:var(--c1);
  }}
  .specs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:8px 16px; margin-top:10px; }}
  .spec {{ display:flex; justify-content:space-between; gap:8px; border-bottom:1px dashed #E2E8F0; padding-bottom:5px; }}
  .spec-k {{ color:#64748B; font-size:12px; }}
  .mono {{ font-family:"Cascadia Code","SF Mono",Consolas,monospace; direction:ltr; unicode-bidi:isolate; letter-spacing:.4px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  thead th {{ text-align:right; color:#64748B; font-size:11px; font-weight:700; padding:6px 8px; border-bottom:1px solid #E2E8F0; }}
  tbody td {{ padding:9px 8px; border-bottom:1px solid #F1F5F9; vertical-align:middle; }}
  tbody tr:last-child td {{ border-bottom:none; }}
  .t-name {{ font-weight:700; color:#111827; white-space:nowrap; }}
  .t-detail {{ color:#475569; }}
  .t-status {{ white-space:nowrap; text-align:left; }}
  .dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-left:6px; }}
  .pill {{ padding:3px 9px; border-radius:10px; font-size:11px; font-weight:700; }}
  .notes p {{ margin:0; color:#475569; }}
  .foot {{ margin-top:18px; padding:14px 4px; color:#94A3B8; font-size:11px; display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; }}
  @media print {{
    body {{ background:#fff; }}
    .page {{ padding:0; max-width:none; }}
    .brand {{ border-radius:0; }}
    .card {{ border:none; box-shadow:none; break-inside:avoid; }}
    .foot {{ color:#64748B; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="brand">
    <div>
      <h1>{self._e(shop)}</h1>
      <div class="sub">تقرير فحص جهاز — {self._e(self._now_str())}</div>
    </div>
    <div class="logo">HF</div>
  </div>
  <div class="result">
    <span>{result_label}</span>
    <span class="meta">{self._e(diag.get("summary") or "")} · الفني: {self._e(tech)}</span>
  </div>
  <section class="card device">
    <div>
      <div class="name">{self._e(self._device_label(device))}</div>
      <span class="status-chip">{self._e(_DEVICE_STATUS_LABEL.get(str(device.get("status")), ""))}</span>
      {'<div class="sub" style="margin-top:6px;color:#64748B;font-size:12px">' + self._e(customer_bits) + "</div>" if customer_bits else ""}
    </div>
    <div class="specs">{spec_html}</div>
  </section>
  {"".join(section_html_parts)}
  {notes_html}
  <div class="foot">
    <span>أُنشئ تلقائيًا بواسطة HF | إتش-إف</span>
    <span>النتائج مسجلة محليًا في الورشة — {self._e(str(diag.get("started_at") or ""))}</span>
  </div>
</div>
</body>
</html>
"""

    # ---- registry ---------------------------------------------------------

    def create_report(self, diagnosis_id: int) -> int:
        """Register a generated report (metadata row) and return its id."""
        data = self.build_report(diagnosis_id)
        if data is None:
            raise ValueError(f"no report for diagnosis {diagnosis_id}")
        device = data["device"]
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO reports(diagnosis_id, device_id, title, created_at) VALUES (?,?,?,?)",
                (
                    diagnosis_id,
                    int(device["id"]),
                    f"تقرير فحص {self._device_label(device)}",
                    self._now_str(),
                ),
            )
            return int(cur.lastrowid)

    def list_reports(self, limit: int = 30, device_id: int | None = None) -> list[dict[str, Any]]:
        sql = """SELECT r.id, r.device_id, r.diagnosis_id, r.title, r.created_at,
                        d.brand, d.model, d.imei, d.status AS device_status,
                        dg.result, dg.summary
                 FROM reports r
                 LEFT JOIN devices d ON d.id=r.device_id
                 LEFT JOIN diagnoses dg ON dg.id=r.diagnosis_id
                 WHERE 1=1"""
        params: list[Any] = []
        if device_id is not None:
            sql += " AND r.device_id=?"
            params.append(device_id)
        sql += " ORDER BY r.created_at DESC, r.id DESC LIMIT ?"
        params.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


__all__ = ["ReportService", "ACCENTS"]
