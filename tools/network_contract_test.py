# -*- coding: utf-8 -*-
"""Static network contract checks.

This test does not require Flask. It verifies that client endpoints and server
routes stay aligned and that Android/APK packaging remains server-free.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def extract_client_endpoints() -> set[str]:
    tree = ast.parse(read("database/connection_rest.py"))
    endpoints: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_request":
            if len(node.args) >= 2:
                ep = node.args[1]
                if isinstance(ep, ast.Constant) and isinstance(ep.value, str):
                    endpoints.add(ep.value)
                elif isinstance(ep, ast.JoinedStr):
                    parts = []
                    for val in ep.values:
                        if isinstance(val, ast.Constant) and isinstance(val.value, str):
                            parts.append(val.value)
                        elif isinstance(val, ast.FormattedValue):
                            parts.append("{var}")
                    endpoints.add("".join(parts))
    return endpoints


def extract_server_routes() -> set[str]:
    text = read("server/flask_server.py")
    routes = set(re.findall(r"@app\.(?:get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']", text))
    normalized = set()
    for route in routes:
        route = re.sub(r"<int:[^>]+>", "{var}", route)
        route = re.sub(r"<path:[^>]+>", "{var}", route)
        route = re.sub(r"<[^>]+>", "{var}", route)
        normalized.add(route)
    return normalized


def route_matches(endpoint: str, routes: set[str]) -> bool:
    if endpoint in routes:
        return True
    pattern = re.escape(endpoint).replace(re.escape("{var}"), r"[^/]+") + r"$"
    return any(re.fullmatch(pattern, r) or re.fullmatch(re.escape(r).replace(re.escape("{var}"), r"[^/]+") + r"$", endpoint) for r in routes)


def assert_apk_safe() -> None:
    pyproject = read("pyproject.toml")
    forbidden = ["Flask", "waitress", "server*", "flask_server", "run_server"]
    for token in forbidden:
        assert token not in pyproject, f"APK pyproject must not package server dependency/module: {token}"
    assert '"services*"' in pyproject, "services package must be included for NetworkService imports"

    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("server/") or rel.startswith("tools/"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "flask" not in text.lower(), f"APK-side module imports/refers to Flask: {rel}"
        assert "waitress" not in text.lower(), f"APK-side module imports/refers to Waitress: {rel}"


def main() -> int:
    client = extract_client_endpoints()
    server = extract_server_routes()
    missing = sorted(ep for ep in client if not route_matches(ep, server))
    assert not missing, "Client endpoints without matching server route: " + ", ".join(missing)
    assert "/api/health" in client and "/api/health" in server
    assert_apk_safe()
    print("✅ network_contract_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
