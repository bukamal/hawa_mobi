# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Any, Dict, List

from auth.session import UserSession
from database.repositories.base_repo import BaseRepository
from services.batch_payment_service import (
    create_payment_batch_in_transaction,
    delete_payment_batch_in_transaction,
    get_payment_batch,
    list_outstanding_claims,
)


class BatchPaymentRepository(BaseRepository):
    def list_outstanding(
        self,
        *,
        company_name: str | None = None,
        person_name: str | None = None,
        direction: str | None = None,
        currency_code: str | None = None,
    ) -> List[Dict[str, Any]]:
        params = {
            "company_name": company_name,
            "person_name": person_name,
            "direction": direction,
            "currency_code": currency_code,
        }
        if self.data.is_remote():
            return self.db.get_rest_client().get_batch_outstanding(params)
        return list_outstanding_claims(self.db.get_connection(), **params)

    def list_party_scopes(self) -> List[Dict[str, Any]]:
        rows = self.list_outstanding()
        scopes: Dict[tuple, Dict[str, Any]] = {}
        for row in rows:
            direction = "received" if row.get("type") == "incoming" else "paid"
            code = row.get("currency_original") or "USD"
            company = str(row.get("company_name") or "").strip()
            person = str(row.get("person_name") or "").strip()
            remaining = float(row.get("remaining_amount_original") or 0)
            company_key = (company, "", direction, code)
            item = scopes.setdefault(company_key, {
                "company_name": company,
                "person_name": "",
                "direction": direction,
                "currency_original": code,
                "remaining_amount_original": 0.0,
                "claims_count": 0,
                "scope": "company",
            })
            item["remaining_amount_original"] += remaining
            item["claims_count"] += 1
            if person:
                person_key = (company, person, direction, code)
                pitem = scopes.setdefault(person_key, {
                    "company_name": company,
                    "person_name": person,
                    "direction": direction,
                    "currency_original": code,
                    "remaining_amount_original": 0.0,
                    "claims_count": 0,
                    "scope": "person",
                })
                pitem["remaining_amount_original"] += remaining
                pitem["claims_count"] += 1
        return sorted(
            scopes.values(),
            key=lambda item: (
                0 if item["direction"] == "received" else 1,
                item["company_name"], item["person_name"], item["currency_original"],
            ),
        )

    def add(self, data: Dict[str, Any], *, user_id: int | None = None) -> Dict[str, Any]:
        if self.data.is_remote():
            return self.db.get_rest_client().add_payment_batch(data)
        conn = self.db.get_connection()
        user = UserSession.get_current() or {}
        uid = int(user_id or user.get("id") or 1)
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = create_payment_batch_in_transaction(
                conn,
                company_name=data.get("company_name"),
                person_name=data.get("person_name") or "",
                direction=data.get("direction"),
                amount=data.get("amount"),
                currency_code=data.get("currency_original") or data.get("currency") or "USD",
                date=data.get("date") or datetime.datetime.now().strftime("%Y-%m-%d"),
                payment_method=data.get("payment_method") or "cash",
                reference_number=data.get("reference_number") or "",
                notes=data.get("notes") or "",
                payer_type=data.get("payer_type"),
                payer_name=data.get("payer_name") or "",
                allocation_mode=data.get("allocation_mode") or "oldest",
                allocations=data.get("allocations") or [],
                user_id=uid,
                username=user.get("username", ""),
            )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise

    def get(self, batch_id_or_reference: int | str) -> Dict[str, Any]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_payment_batch(batch_id_or_reference)
        return get_payment_batch(self.db.get_connection(), batch_id_or_reference)

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_payment_batches(limit=limit)
        rows = self.db.get_connection().execute(
            "SELECT * FROM payment_batches WHERE status='posted' ORDER BY date DESC, id DESC LIMIT ?",
            (max(1, min(int(limit or 50), 200)),),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, batch_id: int, *, reason: str, user_id: int | None = None) -> Dict[str, Any]:
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValueError("سبب حذف الدفعة المجمعة مطلوب")
        if self.data.is_remote():
            return self.db.get_rest_client().delete_payment_batch(int(batch_id), {"reason": clean_reason})
        conn = self.db.get_connection()
        user = UserSession.get_current() or {}
        uid = int(user_id or user.get("id") or 1)
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = delete_payment_batch_in_transaction(
                conn,
                int(batch_id),
                reason=clean_reason,
                user_id=uid,
                username=user.get("username", ""),
            )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
