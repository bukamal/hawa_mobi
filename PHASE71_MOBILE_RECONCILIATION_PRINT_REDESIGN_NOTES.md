# Phase 71 — Mobile Reconciliation Print Redesign

This phase redesigns Android account statement printing for real phone/WhatsApp use.

## Main changes

- Reconciliation statement is now mobile-first and card-based instead of a wide table.
- WhatsApp/general share uses the reconciliation statement by default.
- Detailed print remains available through the print button and uses a constrained five-column layout.
- Passenger, service, and reference details are folded into the statement body instead of being separate narrow columns.
- Phone, email, money, and references are LTR-isolated to avoid RTL wrapping issues.
- Long service references are shortened in reconciliation output while full references remain in detailed print.
- Header/footer are unified across statement templates.
- Matching disclaimer and 48-hour review note are preserved.

## Validation

- `tools/professional_statement_layout_smoke_test.py`
- `tools/report_action_share_print_whatsapp_smoke_test.py`
- `tools/service_components_embassy_transport_smoke_test.py`
