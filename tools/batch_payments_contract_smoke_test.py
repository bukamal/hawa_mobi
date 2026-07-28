#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


migrations = text("database/migrations.py")
for token in (
    "CREATE TABLE IF NOT EXISTS payment_batches",
    "CREATE TABLE IF NOT EXISTS payment_allocations",
    "batch_id INTEGER",
    "schema_version','27",
):
    assert token in migrations, token

service = text("services/batch_payment_service.py")
for token in (
    "create_payment_batch_in_transaction",
    "list_outstanding_claims",
    "ensure_batch_credit",
    "reclassify_allocations_as_credit",
    "customer_credit",
    "supplier_advance",
):
    assert token in service, token

repo = text("database/repositories/batch_payment_repo.py")
for token in ("class BatchPaymentRepository", "list_party_scopes", "allocation_mode", "delete_payment_batch_in_transaction"):
    assert token in repo, token

view = text("views/dialogs/batch_payment_dialog.py")
for token in (
    "دفعة مجمعة",
    "تلقائيًا على الأقدم",
    "توزيع يدوي",
    "رصيد دائن",
    "BatchPaymentHistoryDialog",
):
    assert token in view, token

reminders = text("views/payment_reminders_mobile_view.py")
for token in ("BatchPaymentDialog", "دفعة مجمعة", "توزيع دفعة", "BatchPaymentHistoryDialog"):
    assert token in reminders, token

payment_repo = text("database/repositories/payment_repo.py")
assert "جزء من دفعة مجمعة" in payment_repo

server = text("server/flask_server.py")
for token in (
    "supports_batch_payments",
    "/api/payment-batches/outstanding",
    '@app.post("/api/payment-batches")',
    '@app.delete("/api/payment-batches/<int:batch_id>")',
):
    assert token in server, token

rest = text("database/connection_rest.py")
for method in (
    "get_batch_outstanding",
    "get_payment_batches",
    "get_payment_batch",
    "add_payment_batch",
    "delete_payment_batch",
):
    assert f"def {method}" in rest, method

print("PHASE108_BATCH_PAYMENTS_CONTRACT_OK")
