#!/usr/bin/env python3
"""Patch Flet's generated Android project for scheduled local notifications.

flutter_local_notifications requires reboot receivers and Java core library
 desugaring. The patch is idempotent and runs after Flet generates build/flutter.
"""
from __future__ import annotations

import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)
A = f"{{{ANDROID_NS}}}"


def patch_manifest(path: Path) -> bool:
    tree = ET.parse(path)
    root = tree.getroot()
    changed = False
    permissions = {
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.RECEIVE_BOOT_COMPLETED",
    }
    existing_permissions = {
        node.attrib.get(A + "name") for node in root.findall("uses-permission")
    }
    for name in sorted(permissions - existing_permissions):
        node = ET.Element("uses-permission")
        node.set(A + "name", name)
        root.insert(0, node)
        changed = True

    app = root.find("application")
    if app is None:
        raise RuntimeError(f"No <application> in {path}")
    receivers = {node.attrib.get(A + "name"): node for node in app.findall("receiver")}

    def ensure_receiver(name: str, *, boot: bool = False):
        nonlocal changed
        receiver = receivers.get(name)
        if receiver is None:
            receiver = ET.SubElement(app, "receiver")
            receiver.set(A + "name", name)
            receiver.set(A + "exported", "false")
            changed = True
        if boot and receiver.find("intent-filter") is None:
            intent = ET.SubElement(receiver, "intent-filter")
            for action_name in (
                "android.intent.action.BOOT_COMPLETED",
                "android.intent.action.MY_PACKAGE_REPLACED",
                "android.intent.action.QUICKBOOT_POWERON",
                "com.htc.intent.action.QUICKBOOT_POWERON",
            ):
                action = ET.SubElement(intent, "action")
                action.set(A + "name", action_name)
            changed = True

    ensure_receiver("com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver")
    ensure_receiver("com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver", boot=True)
    ensure_receiver("com.dexterous.flutterlocalnotifications.ActionBroadcastReceiver")
    if changed:
        tree.write(path, encoding="utf-8", xml_declaration=True)
    return changed


def patch_gradle(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    if path.suffix == ".kts":
        if "isCoreLibraryDesugaringEnabled = true" not in text:
            marker = "compileOptions {"
            text = text.replace(marker, marker + "\n        isCoreLibraryDesugaringEnabled = true", 1)
        if "multiDexEnabled = true" not in text:
            marker = "defaultConfig {"
            text = text.replace(marker, marker + "\n        multiDexEnabled = true", 1)
        dependency = 'coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")'
        if dependency not in text:
            marker = "dependencies {"
            if marker in text:
                text = text.replace(marker, marker + "\n    " + dependency, 1)
            else:
                text += "\n\ndependencies {\n    " + dependency + "\n}\n"
    else:
        if "coreLibraryDesugaringEnabled true" not in text:
            marker = "compileOptions {"
            text = text.replace(marker, marker + "\n        coreLibraryDesugaringEnabled true", 1)
        if "multiDexEnabled true" not in text:
            marker = "defaultConfig {"
            text = text.replace(marker, marker + "\n        multiDexEnabled true", 1)
        dependency = 'coreLibraryDesugaring "com.android.tools:desugar_jdk_libs:2.1.4"'
        if dependency not in text:
            marker = "dependencies {"
            if marker in text:
                text = text.replace(marker, marker + "\n    " + dependency, 1)
            else:
                text += "\n\ndependencies {\n    " + dependency + "\n}\n"
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def find_one(root: Path, names: tuple[str, ...]) -> Path:
    matches = []
    for name in names:
        matches.extend(root.rglob(name))
    matches = [p for p in matches if "/app/" in p.as_posix() or p.parent.name == "app"]
    if not matches:
        raise FileNotFoundError(f"Could not find {names} under {root}")
    return sorted(matches, key=lambda p: len(p.parts))[0]


def patch(root: Path) -> dict:
    manifest = find_one(root, ("AndroidManifest.xml",))
    gradle = find_one(root, ("build.gradle", "build.gradle.kts"))
    return {
        "manifest": str(manifest),
        "manifest_changed": patch_manifest(manifest),
        "gradle": str(gradle),
        "gradle_changed": patch_gradle(gradle),
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "build/flutter").resolve()
    result = patch(root)
    print("phase109 Android notifications patch:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
