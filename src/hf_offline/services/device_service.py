"""Device (phone/tablet) repository + domain logic.

The shop's work queue: add a phone under repair, track its status through
the lifecycle (in_queue → in_repair → diagnosing → done), and look up
devices for the diagnosis flow. IMEI input is validated with the standard
Luhn-15 check before storage so a fat-fingered digit never pollutes
reports or the export.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Mapping

from hf_offline.core.database import Database

STATUSES = ("in_queue", "in_repair", "diagnosing", "done")

_STATUS_LABELS = {
    "in_queue": "قيد الانتظار",
    "in_repair": "قيد الإصلاح",
    "diagnosing": "قيد الفحص",
    "done": "مكتمل",
}

_IMEI_RE = re.compile(r"^\d{14,15}$")


def validate_imei(imei: str) -> bool:
    """Standard IMEI check: 15 digits, Luhn checksum on the full value.

    Accepts 15 digits only (14-digit inputs are incomplete, not valid).
    An empty string is "no IMEI recorded" — that is allowed for a device
    row but is not a *valid* IMEI.
    """
    digits = str(imei or "").strip().replace(" ", "")
    if not _IMEI_RE.match(digits) or len(digits) != 15:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DeviceService:
    def __init__(self, db: Database):
        self.db = db

    # ---- queries ---------------------------------------------------------

    def list(self, *, status: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM devices"
        clauses: list[str] = []
        params: list[Any] = []
        if status in STATUSES:
            clauses.append("status = ?")
            params.append(status)
        if search:
            like = f"%{search.strip()}%"
            clauses.append("(brand LIKE ? OR model LIKE ? OR serial LIKE ? OR imei LIKE ? OR imei2 LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?)")
            params.extend([like] * 7)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC, id DESC"
        with self.db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get(self, device_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        return dict(row) if row else None

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in STATUSES}
        out["total"] = 0
        with self.db.connect() as conn:
            for row in conn.execute("SELECT status, COUNT(*) AS n FROM devices GROUP BY status").fetchall():
                status = str(row["status"])
                out[status] = int(row["n"])
                out["total"] += int(row["n"])
        return out

    def labels(self) -> dict[str, str]:
        return dict(_STATUS_LABELS)

    # ---- mutations -------------------------------------------------------

    def add(
        self,
        *,
        serial: str = "",
        imei: str = "",
        imei2: str = "",
        brand: str = "",
        model: str = "",
        color: str = "",
        os_version: str = "",
        customer_name: str = "",
        customer_phone: str = "",
        notes: str = "",
        status: str = "in_queue",
    ) -> int:
        if status not in STATUSES:
            raise ValueError(f"unknown device status: {status!r}")
        with self.db.transaction() as conn:
            cur = conn.execute(
                """INSERT INTO devices(
                    serial, imei, imei2, brand, model, color, os_version,
                    customer_name, customer_phone, notes, status,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?, ?, ?)""",
                (
                    serial.strip() or None,
                    imei.strip() or None,
                    imei2.strip() or None,
                    brand.strip() or None,
                    model.strip() or None,
                    color.strip() or None,
                    os_version.strip() or None,
                    customer_name.strip() or None,
                    customer_phone.strip() or None,
                    notes.strip(),
                    status,
                    _now(),
                    _now(),
                ),
            )
            return int(cur.lastrowid)

    def update(self, device_id: int, **fields: Any) -> None:
        allowed = {
            "serial", "imei", "imei2", "brand", "model", "color", "os_version",
            "customer_name", "customer_phone", "notes", "status",
        }
        cols = [k for k in fields if k in allowed]
        if not cols:
            return
        if "status" in cols and cols["status"] not in STATUSES:
            raise ValueError(f"unknown device status: {fields['status']!r}")
        values = [None if fields[c] is None else str(fields[c]).strip() for c in cols]
        set_sql = ", ".join(f"{c}=? " for c in cols)
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE devices SET {set_sql} updated_at=? WHERE id=?",
                (*values, _now(), device_id),
            )

    def set_status(self, device_id: int, status: str) -> None:
        self.update(device_id, status=status)

    def delete(self, device_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM devices WHERE id=?", (device_id,))

    def find_by_imei(self, imei: str) -> dict[str, Any] | None:
        digits = str(imei or "").strip()
        if not digits:
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM devices WHERE imei=? OR imei2=? LIMIT 1", (digits, digits)).fetchone()
        return dict(row) if row else None


__all__ = ["DeviceService", "STATUSES", "validate_imei"]
