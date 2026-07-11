# Phase 65 — WhatsApp cache-only file share

WhatsApp file sharing now first uses an app-cache copy instead of the public Downloads/MediaStore copy.

Changes:
- Copy generated report into Android cache: `hawaa_whatsapp_share/`.
- Try FileProvider content URI if available.
- Fall back to cache file URI after disabling FileUriExposure guard.
- For WhatsApp, remove `EXTRA_TEXT` so WhatsApp cannot send text-only and drop the attachment.
- Add `ClipData` and `grantUriPermission` for read access.
- Keep MediaStore/Downloads as fallback for general share and if cache-only fails.
