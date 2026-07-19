# Phase 105 — Android Modal, Financial RTL and Layout Fixes

Version: **1.0.49**

## Scope

This phase addresses defects reproduced from real Android screenshots:

- Persistent blank white surface after closing AlertDialog.
- Negative money signs and currency symbols reordered by RTL.
- Financial values clipped with ellipsis.
- Content and floating buttons colliding with the bottom NavigationBar.
- Oversized report filters and duplicated dashboard/account actions.

## Modal architecture

`AlertDialog` is no longer attached as a native Flutter dialog route. `open_control()` converts it into a normal full-screen `Stack` inside `page.overlay`:

- translucent barrier;
- centered modern card;
- original title/content/actions reused;
- no `show_dialog`, `pop_dialog`, or `page.close()`;
- `close_control()` removes the complete host atomically;
- nested dialogs restore the prior logical dialog pointer;
- `close_all_dialogs()` removes every host without touching FilePicker services.

This eliminates the modal route that remained as a white rectangle until Android Back.

## Financial RTL

Added `CurrencyManager.format_amount_ui()`:

- Western currencies render as `-$5,497.00`;
- Arabic currency abbreviations render after the number;
- LRI/PDI bidi isolation prevents sign movement;
- financial Text controls use `rtl=False`;
- critical monetary values no longer use ellipsis;
- constrained account/dashboard tiles use compact display when needed.

## Layout corrections

- NavigationBar height normalized to 76dp.
- FAB location forced to `END_FLOAT`.
- Dynamic bottom clearances: 104dp normally, 132dp with FAB.
- Applied bottom clearance to dashboard, accounts, reports, company details, settings, audit and users.
- Bottom navigation label shortened from `حسابات هوى الشام` to `الحسابات`.
- Company card duplicated detail badge removed; the whole card remains tappable.
- Company operation access moved to a compact three-dot action.
- Admin role no longer uses the destructive red semantic color.
- Dashboard duplicate navigation shortcuts removed.
- Report filters collapse after applying and can be reopened with `تعديل الفلاتر` while export remains accessible.

## Validation

- `compileall`: passed.
- Full project `quality_gate.py`: passed.
- Runtime custom modal open/close/nested cleanup tests: passed.
- Financial bidi/negative-sign test: passed.
- Android navigation, account, report, authentication and admin UI smoke tests: passed.
- APK release preflight: passed.

An actual APK was not built in this environment. The fix must still be installed on a physical Android device to verify the Flutter rendering path across OEMs.
