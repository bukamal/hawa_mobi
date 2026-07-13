# Phase 76 — CI API contract and quality-gate fix

Release: 1.1.1

## Fixed

- Replaced quote-style-dependent REST endpoint assertions with Python AST checks.
- The static fallback now validates `RestClient` method names and endpoint string literals regardless of whether Black/Ruff uses single or double quotes.
- GitHub Actions installs `server/requirements.txt`, so the comprehensive contract test executes the live Flask API path in CI.
- The quality gate now inherits stdout/stderr instead of piping them, preventing Flet helper processes from keeping pipe handles open and delaying successful tests.

## Compatibility

No database schema or backup format change was introduced. Legacy database import and rollback behavior from version 1.1.0 remain unchanged.

## Validation

- Static fallback without Flask: passed.
- Live Flask API contract: passed.
- All 50 quality-gate scripts: passed in isolated data directories.
