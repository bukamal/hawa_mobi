# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import quote


class Picked:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def main() -> int:
    root = tempfile.mkdtemp(prefix="hawaa_picker_resolve_")
    os.environ["HAWAA_DATA_DIR"] = os.path.join(root, "data")
    os.environ["FLET_APP_STORAGE_TEMP"] = os.path.join(root, "tmp")
    public = os.path.join(root, "Download")
    os.environ["PUBLIC_DOWNLOADS"] = public
    os.makedirs(os.path.join(public, "Hawaa"), exist_ok=True)

    from database.migrations import init_database
    from services.file_export_service import FileExportService

    init_database()
    backup = FileExportService.create_backup_archive()
    assert os.path.exists(backup)

    # Direct path returned by FilePicker.
    assert FileExportService.resolve_picker_file_path(Picked(path=backup, name=os.path.basename(backup))) == backup

    # file:// URI returned by FilePicker.
    file_uri = "file://" + quote(backup)
    assert FileExportService.resolve_picker_file_path(Picked(path=file_uri, name=os.path.basename(backup))) == backup

    # Android display-name only: locate in Download/Hawaa fallback.
    target = os.path.join(public, "Hawaa", os.path.basename(backup))
    Path(target).write_bytes(Path(backup).read_bytes())
    resolved = FileExportService.resolve_picker_file_path(Picked(name=os.path.basename(backup), size=os.path.getsize(target)))
    assert resolved == target, resolved

    # content:// must not crash when no Java bridge is available in desktop tests.
    unresolved = FileExportService.resolve_picker_file_path(Picked(uri="content://com.android.providers.downloads/document/123", name="missing.zip"))
    assert unresolved is None
    details = FileExportService.describe_picker_file(Picked(uri="content://x", name="a.zip", size=7))
    assert "uri=content://x" in details and "name=a.zip" in details
    print("✅ backup_picker_resolution_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
