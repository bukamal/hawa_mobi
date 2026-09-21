"""Diagnosis engine: the test plan, live execution state, and results.

A *diagnosis* is one session against one device: it starts (the device is
marked ``diagnosing``), accumulates one ``diagnosis_items`` row per
executed test, and finishes with an aggregate result (``passed`` when
nothing failed, ``failed`` when any test failed, ``incomplete`` when the
session was closed early).

Test execution itself is pluggable: ``run_probe`` is where the real
hardware bridge (QFIL / preloader / ADB) will call out to the phone. In
the current build it runs the local probe — deterministic and injectable
(``set_probe``) so the full flow is testable end-to-end without hardware,
and a repair bench can later swap in a real probe without touching the UI.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable

from hf_offline.core.database import Database
from hf_offline.services.device_service import DeviceService

# category -> ordered test names (Arabic, bench-friendly phrasing)
TEST_CATALOG: dict[str, list[str]] = {
    "الشاشة": ["إضاءة وتوهج", "ألوان ودقة الألوان", "مناطق ميتة وشوائب", "دقة اللمس الحساسة"],
    "اللمسية": ["استجابة المس", "تعدد اللمسات", "دقة المس", "خطوط شبحية"],
    "الكاميرا": ["الكاميرا الخلفية", "الكاميرا الأمامية", "التركيز البؤري", "الفلاش"],
    "الصوت": ["السماعة الخارجية", "السماعة الداخلية (وسائط)", "الميكروفون", "عزل الصوت"],
    "الحساسات": ["الجيروسكوب", "البوصلة", "حساس القرب", "مستشعر الإضاءة"],
    "البطارية": ["السعة الفعلية", "معدل الشحن", "تسرب الحرارة", "دورات الاستخدام"],
    "الاتصالات": ["شبكة الجوال", "الواي فاي", "البلوتوث", "NFC"],
    "الأداء": ["سرعة المعالج", "ذاكرة RAM", "التخزين الداخلي", "استهلاك الطاقة"],
}

DEFAULT_CATEGORIES: tuple[str, ...] = tuple(TEST_CATALOG.keys())

# A probe takes (category, test_name) and returns
# ("passed" | "failed" | "warning" | "na", detail, duration_ms).
Probe = Callable[[str, str], tuple[str, str, int]]


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _default_probe(category: str, test_name: str) -> tuple[str, str, int]:
    """Local (hardware-less) probe: reports the test as passed with a
    neutral detail line. Real benches replace this via ``set_probe``."""
    return ("passed", f"{test_name} ضمن النطاق المعتمد", 40)


class DiagnosisService:
    def __init__(self, db: Database, devices: DeviceService):
        self.db = db
        self.devices = devices
        self._probe: Probe = _default_probe

    def set_probe(self, probe: Probe | None) -> None:
        """Install a hardware probe (or None to restore the local default)."""
        self._probe = probe or _default_probe

    # ---- catalog ---------------------------------------------------------

    def categories(self) -> list[str]:
        return list(DEFAULT_CATEGORIES)

    def tests(self, category: str) -> list[str]:
        return list(TEST_CATALOG.get(category, ()))

    def plan(self, categories: list[str] | None = None) -> list[tuple[str, str]]:
        """The (category, test_name) pairs that will run, in bench order."""
        cats = categories if categories else self.categories()
        plan: list[tuple[str, str]] = []
        for cat in cats:
            for test in self.tests(cat):
                plan.append((cat, test))
        return plan

    # ---- session lifecycle ----------------------------------------------

    def start(self, device_id: int, categories: list[str] | None = None) -> int:
        """Open a diagnosis session and mark the device ``diagnosing``.

        The full test plan (category|test pairs) is persisted on the row so
        progress and the final report can always know what was *supposed*
        to run, even across an app restart mid-session.
        """
        import json

        plan = [f"{c}|{t}" for c, t in self.plan(categories)]
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO diagnoses(device_id, plan, started_at) VALUES(?,?,?)",
                (device_id, json.dumps(plan), _now()),
            )
            diag_id = int(cur.lastrowid)
        self.devices.set_status(device_id, "diagnosing")
        return diag_id

    def record(
        self,
        diagnosis_id: int,
        category: str,
        test_name: str,
        status: str,
        detail: str = "",
        duration_ms: int = 0,
    ) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute(
                """INSERT INTO diagnosis_items(diagnosis_id, category, test_name, status, detail, duration_ms)
                   VALUES (?,?,?,?,?,?)""",
                (diagnosis_id, category, test_name, status, detail, int(duration_ms or 0)),
            )
            return int(cur.lastrowid)

    def run_probe(self, diagnosis_id: int, category: str, test_name: str) -> dict[str, Any]:
        """Run one test through the installed probe and record it.

        Returns the recorded result as a dict.
        """
        status, detail, duration = self._probe(category, test_name)
        if status not in ("passed", "failed", "warning", "na"):
            status = "warning"
        item_id = self.record(diagnosis_id, category, test_name, status, detail, duration)
        return {
            "id": item_id,
            "category": category,
            "test_name": test_name,
            "status": status,
            "detail": detail,
            "duration_ms": duration,
        }

    def finish(self, diagnosis_id: int, *, incomplete: bool = False) -> dict[str, Any]:
        """Close the session, compute the aggregate result, and move the
        device to its next state (``done`` when passed, ``in_repair`` when
        anything failed — a failed bench means the phone stays in the shop).
        """
        items = self.results(diagnosis_id)
        finished = incomplete and not self._is_finished(diagnosis_id)
        if finished:
            result = "incomplete"
        else:
            statuses = {i["status"] for i in items}
            if "failed" in statuses:
                result = "failed"
            else:
                result = "passed"
        passed = sum(1 for i in items if i["status"] == "passed")
        failed = sum(1 for i in items if i["status"] == "failed")
        summary = f"{passed} ناجح من أصل {len(items)}"
        if failed:
            summary += f"، {failed} فاشل"
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE diagnoses SET finished_at=?, result=?, summary=? WHERE id=?",
                (_now(), result, summary, diagnosis_id),
            )
        diag = self.get(diagnosis_id) or {}
        device_id = int(diag.get("device_id") or 0)
        if device_id:
            self.devices.set_status(device_id, "done" if result == "passed" else "in_repair")
        return {"diagnosis_id": diagnosis_id, "result": result, "summary": summary, "device_id": device_id}

    # ---- reads -----------------------------------------------------------

    def get(self, diagnosis_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM diagnoses WHERE id=?", (diagnosis_id,)).fetchone()
        return dict(row) if row else None

    def results(self, diagnosis_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM diagnosis_items WHERE diagnosis_id=? ORDER BY id",
                (diagnosis_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def group_by_category(self, diagnosis_id: int) -> list[dict[str, Any]]:
        """Results grouped for the report screen: one dict per category."""
        out: list[dict[str, Any]] = []
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM diagnosis_items WHERE diagnosis_id=? ORDER BY category, id",
                (diagnosis_id,),
            ).fetchall()
        for row in rows:
            item = dict(row)
            for group in out:
                if group["category"] == item["category"]:
                    group["items"].append(item)
                    break
            else:
                out.append({"category": item["category"], "items": [item]})
        return out

    def progress(self, diagnosis_id: int) -> dict[str, int]:
        """How many of the session's planned tests have been recorded.

        The planned total comes from the persisted ``plan`` column (so it
        survives an app restart mid-session); a session started before the
        plan column existed falls back to the recorded row count.
        """
        import json

        recorded = len(self.results(diagnosis_id))
        total = 0
        with self.db.connect() as conn:
            row = conn.execute("SELECT plan FROM diagnoses WHERE id=?", (diagnosis_id,)).fetchone()
        if row and row["plan"]:
            try:
                total = len(json.loads(row["plan"]))
            except Exception:
                total = 0
        if total == 0:
            total = recorded
        return {
            "done": recorded,
            "total": total,
            "percent": int(100 * recorded / total) if total else 0,
        }

    def active_for_device(self, device_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM diagnoses WHERE device_id=? AND finished_at IS NULL ORDER BY id DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def latest(self, device_id: int | None = None) -> dict[str, Any] | None:
        if device_id is not None:
            sql = "SELECT * FROM diagnoses WHERE device_id=? AND finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1"
            params: tuple[Any, ...] = (device_id,)
        else:
            sql = "SELECT * FROM diagnoses WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1"
            params = ()
        with self.db.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _is_finished(self, diagnosis_id: int) -> bool:
        diag = self.get(diagnosis_id)
        return bool(diag and diag.get("finished_at"))

__all__ = ["DiagnosisService", "TEST_CATALOG", "DEFAULT_CATEGORIES", "Probe"]
