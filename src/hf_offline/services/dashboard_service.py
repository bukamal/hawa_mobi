"""Dashboard aggregates + the "smart layer": Arabic insight sentences the
shop owner reads in three seconds.

Everything is derived live from the real tables (never cached in a second
place), and the insights follow a small fixed decision table so the text
always matches the numbers shown next to it.
"""

from __future__ import annotations

import datetime
from typing import Any

from hf_offline.core.database import Database
from hf_offline.services.device_service import DeviceService
from hf_offline.services.diagnosis_service import DiagnosisService


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


class DashboardService:
    def __init__(self, db: Database, devices: DeviceService, diagnoses: DiagnosisService):
        self.db = db
        self.devices = devices
        self.diagnoses = diagnoses

    def kpis(self) -> dict[str, int]:
        counts = self.devices.counts()
        with self.db.connect() as conn:
            passed_today = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM diagnosis_items d JOIN diagnoses diag ON diag.id=d.diagnosis_id "
                    "WHERE d.status='passed' AND date(diag.started_at)=date('now','localtime')"
                ).fetchone()["n"]
            )
            failed_today = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM diagnosis_items d JOIN diagnoses diag ON diag.id=d.diagnosis_id "
                    "WHERE d.status='failed' AND date(diag.started_at)=date('now','localtime')"
                ).fetchone()["n"]
            )
            finished_today = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM diagnoses WHERE finished_at IS NOT NULL AND date(finished_at)=date('now','localtime')"
                ).fetchone()["n"]
            )
        return {
            "total": counts["total"],
            "in_queue": counts["in_queue"],
            "in_repair": counts["in_repair"],
            "diagnosing": counts["diagnosing"],
            "done": counts["done"],
            "passed_today": passed_today,
            "failed_today": failed_today,
            "finished_today": finished_today,
        }

    def recent_devices(self, limit: int = 5) -> list[dict[str, Any]]:
        return self.devices.list()[:limit]

    def pending_alerts(self, limit: int = 4) -> list[dict[str, Any]]:
        """Devices waiting on the bench with a failed diagnosis — the things
        the technician should look at first."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT d.id, d.brand, d.model, d.customer_name,
                          (SELECT result FROM diagnoses
                            WHERE device_id=d.id AND finished_at IS NOT NULL
                            ORDER BY finished_at DESC LIMIT 1) AS last_result
                   FROM devices d
                   WHERE d.status IN ('in_repair','in_queue')
                     AND (SELECT result FROM diagnoses
                           WHERE device_id=d.id AND finished_at IS NOT NULL
                           ORDER BY finished_at DESC LIMIT 1)='failed'
                   ORDER BY d.updated_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insights(self) -> list[dict[str, str]]:
        """Smart-layer Arabic insight lines (severity + text).

        Decision table (first match wins for the "headline", the rest are
        secondary lines):
        * device under diagnosis now      -> info
        * failed tests today              -> urgent + top failing test
        * devices awaiting repair         -> warning + count
        * no devices at all               -> info "add first device"
        * otherwise                       -> success "all clear"
        """
        k = self.kpis()
        out: list[dict[str, str]] = []

        if k["diagnosing"] > 0:
            out.append({"severity": "info", "text": f"جارٍ فحص {k['diagnosing']} جهاز الآن في الورشة."})

        with self.db.connect() as conn:
            top_fail = conn.execute(
                """SELECT i.test_name, i.category, COUNT(*) AS n
                   FROM diagnosis_items i JOIN diagnoses dg ON dg.id=i.diagnosis_id
                   WHERE i.status='failed' AND date(dg.started_at)=date('now','localtime')
                   GROUP BY i.category, i.test_name ORDER BY n DESC LIMIT 1"""
            ).fetchone()
        if k["failed_today"] > 0 and top_fail:
            out.append({
                "severity": "urgent",
                "text": f"أنظار صيانة مطلوبة: فشل «{top_fail['test_name']}» في {top_fail['category']} أثناء فحوصات اليوم ({k['failed_today']} اختبارًا فاشلًا).",
            })
        elif k["failed_today"] > 0:
            out.append({"severity": "urgent", "text": f"سُجّل {k['failed_today']} اختبار فاشل اليوم — راجع الأجهزة قيد الإصلاح."})

        if k["in_repair"] > 0:
            out.append({"severity": "warning", "text": f"لديك {k['in_repair']} جهاز قيد الإصلاح بانتظار إعادة الفحص."})

        if k["total"] == 0:
            out.append({"severity": "info", "text": "لا توجد أجهزة في الورشة بعد — أضف أول جهاز لتبدأ."})
        elif not out:
            out.append({"severity": "success", "text": "الورشة بحالة جيدة: لا أجهزة عالقة ولا فحوصات فاشلة اليوم."})

        return out

    def today_summary(self) -> dict[str, Any]:
        k = self.kpis()
        total_tests = k["passed_today"] + k["failed_today"]
        pass_rate = int(100 * k["passed_today"] / total_tests) if total_tests else 0
        return {
            "passed_today": k["passed_today"],
            "failed_today": k["failed_today"],
            "pass_rate": pass_rate,
            "finished_today": k["finished_today"],
        }


__all__ = ["DashboardService"]
