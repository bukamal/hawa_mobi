# -*- coding: utf-8 -*-
"""Flet compatibility helpers for dialogs, transient controls and services.

The APK deliberately pins a FilePicker-stable Flet line for Android backup
restore/logo import.  Newer Flet lines may expose FilePicker in Python while the
Flutter client rejects it at runtime with ``Unknown control: FilePicker``.  Keep
all service controls behind helpers in this module instead of appending them
directly from views.
"""
from __future__ import annotations

import asyncio
import inspect
import threading
import traceback

import flet as ft

ARABIC_FONT_FAMILY = "Arial"
_STACK_ATTR = "_hawaa_dialog_stack"


def _resolve_alignment(lower_name: str, upper_name: str, x: float, y: float):
    """Return an Alignment value across Flet runtime naming variants.

    The pinned Android runtime exposes ``ft.Alignment`` as a type, but does not
    expose enum-like members such as ``ft.Alignment.CENTER``.  The canonical
    Flet value is usually under ``ft.alignment.center``.  Keep a constructor
    fallback so startup cannot fail before Splash/Login.
    """
    try:
        alignment_module = getattr(ft, "alignment", None)
        value = getattr(alignment_module, lower_name, None) if alignment_module is not None else None
        if value is not None:
            return value
    except Exception:
        pass
    try:
        return getattr(ft.Alignment, upper_name)
    except Exception:
        pass
    try:
        return ft.Alignment(x, y)
    except Exception:
        try:
            return ft.Alignment(horizontal=x, vertical=y)
        except Exception:
            return None


ALIGN_CENTER = _resolve_alignment("center", "CENTER", 0, 0)
ALIGN_TOP_LEFT = _resolve_alignment("top_left", "TOP_LEFT", -1, -1)
ALIGN_BOTTOM_RIGHT = _resolve_alignment("bottom_right", "BOTTOM_RIGHT", 1, 1)


def patch_flet_alignment_aliases() -> None:
    """Install legacy ``ft.Alignment.*`` aliases when a runtime omits them.

    This is a defensive guard for older project code and third-party snippets.
    The app source should prefer the compatibility constants above.
    """
    for name, value in {
        "CENTER": ALIGN_CENTER,
        "TOP_LEFT": ALIGN_TOP_LEFT,
        "BOTTOM_RIGHT": ALIGN_BOTTOM_RIGHT,
    }.items():
        if value is None:
            continue
        try:
            if not hasattr(ft.Alignment, name):
                setattr(ft.Alignment, name, value)
        except Exception:
            pass


patch_flet_alignment_aliases()


def _flet_version_tuple():
    """Best-effort Flet version tuple.

    Flet 0.80+ Android builds observed in this project can expose FilePicker in
    Python while the Flutter client rejects it with ``Unknown control: FilePicker``.
    Flet 0.28.x keeps the legacy overlay FilePicker path working on Android.
    """
    try:
        raw = str(getattr(ft, "__version__", "") or "")
    except Exception:
        raw = ""
    parts = []
    for chunk in raw.replace("-", ".").split("."):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _allow_legacy_filepicker_overlay() -> bool:
    """Return True for the FilePicker-stable Flet line pinned by this app.

    The APK must use a real Android picker for backup import/logo selection;
    the fallback path is not sufficient for production.  Flet 0.28.x is the
    pinned line here because it avoids the 0.80+ ``Unknown control: FilePicker``
    regression seen on Android builds.
    """
    return _flet_version_tuple() < (0, 80, 0)


def _overlay(page):
    return getattr(page, "overlay", None)


def _is_dialog_like(control) -> bool:
    """Controls managed by Flet's dialog stack: AlertDialog, DatePicker, etc."""
    try:
        return isinstance(control, ft.DialogControl)
    except Exception:
        # Older/newer Flet may not expose DialogControl as a public symbol.
        try:
            return isinstance(control, (ft.AlertDialog, ft.DatePicker, ft.TimePicker))
        except Exception:
            return False


def _get_stack(page) -> list:
    stack = getattr(page, _STACK_ATTR, None)
    if stack is None:
        stack = []
        try:
            setattr(page, _STACK_ATTR, stack)
        except Exception:
            pass
    return stack


def _remove_from_stack(page, control) -> None:
    try:
        stack = _get_stack(page)
        while control in stack:
            stack.remove(control)
    except Exception:
        pass


def _remove_from_overlay(page, control) -> None:
    try:
        ov = _overlay(page)
        if ov is None:
            return
        for item in list(ov):
            if item is control:
                try:
                    ov.remove(item)
                except Exception:
                    pass
    except Exception:
        pass


def open_control(page: ft.Page, control):
    """Open a dialog/transient control using the native Flet dialog stack first.

    Fallback is the classic overlay/open path.  The local stack lets close_control
    know whether ``page.pop_dialog()`` is safe to call for the exact top dialog.
    """
    if page is None or control is None:
        return None

    if _is_dialog_like(control) and hasattr(page, "show_dialog"):
        try:
            if not getattr(control, "open", False):
                page.show_dialog(control)
            stack = _get_stack(page)
            if control in stack:
                stack.remove(control)
            stack.append(control)
            try:
                page.update()
            except Exception:
                pass
            return None
        except Exception:
            pass

    try:
        ov = _overlay(page)
        if ov is not None and control not in ov:
            ov.append(control)
    except Exception:
        pass
    try:
        control.open = True
    except Exception:
        pass
    try:
        if isinstance(control, ft.AlertDialog):
            page.dialog = control
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass
    return None


def close_control(page: ft.Page, control):
    """Close one exact control reliably.

    For dialogs opened with ``show_dialog`` the correct close operation
    is ``page.pop_dialog()``.  We call it only when the requested control is the
    top item in our stack; otherwise we do a specific fallback close to avoid
    accidentally popping the visible parent dialog while trying to close an
    already-closed DatePicker.
    """
    if page is None or control is None:
        return None

    was_open = bool(getattr(control, "open", False))
    stack = _get_stack(page)
    is_top = bool(stack and stack[-1] is control)

    if _is_dialog_like(control) and was_open and is_top and hasattr(page, "pop_dialog"):
        try:
            page.pop_dialog()
            _remove_from_stack(page, control)
            try:
                control.open = False
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass
            return None
        except Exception:
            pass

    # Specific fallback: never pop an unrelated/top parent dialog here.
    try:
        if hasattr(page, "close") and callable(getattr(page, "close")) and was_open:
            page.close(control)
    except Exception:
        pass
    try:
        control.open = False
    except Exception:
        pass
    _remove_from_stack(page, control)
    _remove_from_overlay(page, control)
    try:
        if getattr(page, "dialog", None) is control:
            page.dialog = None
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass
    return None


def close_all_dialogs(page: ft.Page):
    """Emergency cleanup of all dialog-like controls."""
    if page is None:
        return None
    try:
        stack = _get_stack(page)
        while stack and hasattr(page, "pop_dialog"):
            ctrl = stack.pop()
            try:
                if getattr(ctrl, "open", False):
                    page.pop_dialog()
            except Exception:
                break
    except Exception:
        pass
    try:
        ov = _overlay(page) or []
        for item in list(ov):
            if _is_dialog_like(item):
                try:
                    item.open = False
                except Exception:
                    pass
                try:
                    ov.remove(item)
                except Exception:
                    pass
        page.dialog = None
        page.update()
    except Exception:
        pass
    return None



def run_async_task(page, async_callable, *args, **kwargs):
    """Schedule an async callable without requiring a globally running loop.

    Flet 0.28.x can invoke synchronous view constructors/event handlers outside
    a public ``asyncio`` loop on Android. Calling ``asyncio.create_task(...)``
    there raises ``RuntimeError: no running event loop`` and crashes startup.

    Prefer ``page.run_task`` because it attaches the coroutine to Flet's own
    runtime loop. Keep loop/thread fallbacks for desktop tests and older Flet
    shells so callers can use one helper everywhere.
    """
    async def _runner():
        if inspect.isawaitable(async_callable):
            return await async_callable
        result = async_callable(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _log_failure(prefix: str, exc: BaseException) -> None:
        try:
            print(f"[ERROR] {prefix}: {exc}\n{traceback.format_exc()}", flush=True)
        except Exception:
            pass

    flet_runner = getattr(page, "run_task", None) if page is not None else None
    if callable(flet_runner):
        # Flet's documented form is page.run_task(async_fn, *args, **kwargs).
        if inspect.iscoroutinefunction(async_callable):
            try:
                return flet_runner(async_callable, *args, **kwargs)
            except TypeError:
                pass
            except RuntimeError as exc:
                _log_failure("فشل جدولة المهمة عبر Flet run_task", exc)
            except Exception as exc:
                _log_failure("فشل جدولة المهمة عبر Flet run_task", exc)
        try:
            return flet_runner(_runner)
        except TypeError:
            try:
                return flet_runner(_runner())
            except Exception as exc:
                _log_failure("فشل جدولة المهمة عبر Flet run_task", exc)
        except RuntimeError as exc:
            _log_failure("فشل جدولة المهمة عبر Flet run_task", exc)
        except Exception as exc:
            _log_failure("فشل جدولة المهمة عبر Flet run_task", exc)

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_runner())
        try:
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        except Exception:
            pass
        return task
    except RuntimeError:
        pass
    except Exception as exc:
        _log_failure("فشل جدولة المهمة عبر asyncio", exc)

    def _thread_target():
        try:
            asyncio.run(_runner())
        except Exception as exc:
            _log_failure("فشل تنفيذ المهمة المؤجلة", exc)

    thread_runner = getattr(page, "run_thread", None) if page is not None else None
    if callable(thread_runner):
        try:
            return thread_runner(_thread_target)
        except Exception as exc:
            _log_failure("فشل تشغيل المهمة في Flet thread", exc)

    thread = threading.Thread(target=_thread_target, name="hawaa-async-fallback", daemon=True)
    thread.start()
    return thread


def _filter_constructor_kwargs(constructor, kwargs: dict, always_drop: set[str] | None = None) -> tuple[dict, dict]:
    """Return kwargs accepted by a Flet constructor plus rejected kwargs.

    Android Flet runtime bindings can lag behind Python examples.  Passing a
    new layout argument to an older control constructor raises TypeError during
    screen construction.  Keep that incompatibility here instead of crashing a
    whole view.
    """
    always_drop = always_drop or set()
    rejected = {}
    accepted = {}
    try:
        signature = inspect.signature(constructor)
        params = signature.parameters
        has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        allowed = set(params)
    except Exception:
        has_var_kwargs = False
        allowed = set()

    for key, value in dict(kwargs).items():
        if key in always_drop:
            rejected[key] = value
            continue
        if has_var_kwargs or key in allowed:
            accepted[key] = value
        else:
            rejected[key] = value
    return accepted, rejected


def _construct_with_keyword_fallback(constructor, kwargs: dict, *, always_drop: set[str] | None = None):
    """Construct a Flet control and remove unsupported keyword arguments if needed."""
    accepted, rejected = _filter_constructor_kwargs(constructor, kwargs, always_drop=always_drop)
    try:
        control = constructor(**accepted)
    except TypeError as exc:
        # Last-resort parser for runtimes whose signature is too permissive or
        # unavailable but the constructor still rejects a concrete keyword.
        message = str(exc)
        bad_key = None
        for quote in ("'", '"'):
            marker = "unexpected keyword argument " + quote
            if marker in message:
                bad_key = message.split(marker, 1)[1].split(quote, 1)[0]
                break
        if bad_key and bad_key in accepted:
            rejected[bad_key] = accepted.pop(bad_key)
            control = constructor(**accepted)
        else:
            raise
    try:
        setattr(control, "_hawaa_rejected_kwargs", rejected)
    except Exception:
        pass
    return control


def make_floating_action_button(**kwargs):
    """Create a FloatingActionButton across Flet Android/Desktop variants.

    Flet 0.28.x accepts the visual/action parameters used by the app, but it
    rejects ``margin`` on ``FloatingActionButton``.  The margin belongs to layout
    containers, not to the FAB constructor in this runtime.  A direct call would
    crash a screen with: ``unexpected keyword argument 'margin'``.
    """
    return _construct_with_keyword_fallback(
        ft.FloatingActionButton,
        kwargs,
        always_drop={"margin"},
    )


def make_file_picker(on_result=None):
    """Create FilePicker across Flet versions.

    Some mobile/runtime builds reject ``FilePicker(on_result=...)`` with
    ``unexpected keyword argument 'on_result'``.  The compatible path is to
    instantiate first and then assign ``picker.on_result`` when available.
    """
    picker = None
    if on_result is not None:
        try:
            picker = ft.FilePicker(on_result=on_result)
        except TypeError:
            picker = None
        except Exception:
            picker = None
    if picker is None:
        picker = ft.FilePicker()
        if on_result is not None:
            try:
                picker.on_result = on_result
            except Exception:
                pass
    return picker


def _platform_name(page) -> str:
    """Return a lowercase platform name when Flet exposes one."""
    try:
        value = getattr(page, "platform", "") or ""
        name = getattr(value, "value", value)
        return str(name or "").lower()
    except Exception:
        return ""


def _is_mobile_page(page) -> bool:
    name = _platform_name(page)
    return "android" in name or "ios" in name


def attach_service_control(page: ft.Page, control):
    """Attach service controls such as FilePicker/PermissionHandler safely.

    Flet changed FilePicker/PermissionHandler from overlay-style controls to
    service controls in recent runtimes.  Some Android/Web builds show a fatal
    red overlay: ``Unknown control: FilePicker`` when the service is appended to
    ``page.overlay``.  Therefore we prefer ``page.services`` when available and
    never force service controls into overlay on mobile.
    """
    if page is None or control is None:
        return control

    attached = False

    # Newer Flet service API.
    for attr in ("services", "_services"):
        try:
            services = getattr(page, attr, None)
            if services is not None and control not in services:
                services.append(control)
                attached = True
                break
        except Exception:
            pass

    # Android builds on Flet 0.80+ may expose FilePicker in Python while the
    # Flutter client rejects it as an overlay control (red screen:
    # ``Unknown control: FilePicker``).  However Flet 0.28.x is the stable
    # line for this app and requires the legacy overlay path.
    if not attached and _is_mobile_page(page) and not _allow_legacy_filepicker_overlay():
        try:
            setattr(control, "_hawaa_service_attached", False)
        except Exception:
            pass
        return control

    # Legacy desktop/web/mobile fallback.  This is required for the pinned
    # Flet 0.28.x APK so Android opens the native file picker instead of using
    # the internal fallback-only import path.
    if not attached:
        try:
            ov = _overlay(page)
            if ov is not None and control not in ov:
                ov.append(control)
                attached = True
        except Exception:
            pass

    try:
        setattr(control, "_hawaa_service_attached", bool(attached))
    except Exception:
        pass
    if attached:
        try:
            page.update()
        except Exception:
            pass
    return control


def service_control_attached(control) -> bool:
    try:
        return bool(getattr(control, "_hawaa_service_attached", False))
    except Exception:
        return False


def filepicker_unavailable_message() -> str:
    return (
        "منتقي الملفات غير مدعوم في نسخة Flet/Android الحالية أو لم يكتمل تسجيله في الواجهة. "
        "استخدم نسخة APK مبنية بـ Flet يدعم FilePicker، أو استخدم مسار النسخة الاحتياطي داخل تخزين التطبيق كحل مؤقت."
    )

def show_snackbar(page: ft.Page, message: str, is_error: bool = False, duration: int = 3000):
    snack = ft.SnackBar(
        content=ft.Text(message, size=13),
        bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN,
        duration=duration,
    )
    open_control(page, snack)
    return snack


def apply_arabic_ui_defaults(page: ft.Page):
    """Use a common Arabic-capable system font to avoid square/garbled glyphs."""
    try:
        page.theme = ft.Theme(font_family=ARABIC_FONT_FAMILY)
        page.dark_theme = ft.Theme(font_family=ARABIC_FONT_FAMILY)
    except Exception:
        pass
    try:
        page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("ar"), ft.Locale("en")],
            current_locale=ft.Locale("ar"),
        )
    except Exception:
        pass
