# -*- coding: utf-8 -*-
"""Small interaction helpers for responsive Flet views.

The pinned Android runtime does not guarantee a public asyncio loop inside every
synchronous event callback.  These helpers therefore schedule through the
project's ``run_async_task`` compatibility layer.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from views.flet_compat import run_async_task


class DebouncedAction:
    """Run only the latest triggered action after a short quiet period."""

    def __init__(self, page, callback: Callable[[Any], Any], delay_seconds: float = 0.30):
        self._page = page
        self._callback = callback
        self._delay = max(0.0, float(delay_seconds))
        self._generation = 0

    def trigger(self, event=None):
        self._generation += 1
        generation = self._generation

        async def _wait_and_run():
            await asyncio.sleep(self._delay)
            if generation != self._generation:
                return
            result = self._callback(event)
            if asyncio.iscoroutine(result):
                await result

        return run_async_task(self._page, _wait_and_run)

    def cancel(self):
        self._generation += 1
