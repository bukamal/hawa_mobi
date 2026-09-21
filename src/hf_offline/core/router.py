"""Framework-agnostic route registry with a real back-stack.

Same contract as the reference app's router (pure Python, no flet import,
unit-testable): the shell injects a ``render`` callback; nav-bar/sidebar
taps use ``go(..., reset=True)`` so tabs behave like tabs (back exits,
doesn't walk every previously tapped tab), while in-app transitions push
and the hardware back button pops properly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = ["Route", "RouteDenied", "Router"]

Render = Callable[[str, dict], None]


class RouteDenied(Exception):
    """Raised (and reported through ``on_denied``) when a route is unknown,
    has no renderer, or fails the permission check."""


@dataclass(slots=True)
class Route:
    key: str
    label: str = ""
    subtitle: str = ""
    icon: Any = None
    permission: str | None = None
    render: Render | None = None
    replace_current: bool = False
    on_leave: Render | None = None


@dataclass(slots=True)
class Router:
    home: str = "dashboard"
    render: Render | None = None
    can_render: Callable[[Route], bool] | None = None
    on_denied: Callable[[Exception, str, dict], None] | None = None
    on_change: Callable[[Route], None] | None = None

    _routes: dict[str, Route] = field(default_factory=dict, repr=False)
    _current: Route | None = field(default=None, repr=False)
    _current_kwargs: dict = field(default_factory=dict, repr=False)
    _stack: list[tuple[str, dict]] = field(default_factory=list, repr=False)

    # ---- registry ----------------------------------------------------------

    def register(
        self,
        key: str,
        *,
        label: str = "",
        subtitle: str = "",
        icon: Any = None,
        permission: str | None = None,
        render: Render | None = None,
        replace_current: bool = False,
        on_leave: Render | None = None,
    ) -> Route:
        route = Route(
            key=key,
            label=label,
            subtitle=subtitle,
            icon=icon,
            permission=permission,
            render=render,
            replace_current=replace_current,
            on_leave=on_leave,
        )
        self._routes[key] = route
        return route

    def add(self, route: Route) -> Route:
        self._routes[route.key] = route
        return route

    def get(self, key: str) -> Route | None:
        return self._routes.get(key)

    @property
    def routes(self) -> dict[str, Route]:
        return dict(self._routes)

    # ---- state -------------------------------------------------------------

    @property
    def current(self) -> str | None:
        return self._current.key if self._current else None

    @property
    def current_route(self) -> Route | None:
        return self._current

    @property
    def stack(self) -> list[str]:
        """History below the current screen, oldest first (excludes current)."""
        return [key for key, _ in self._stack]

    @property
    def path(self) -> list[str]:
        keys = [key for key, _ in self._stack]
        if self._current is not None:
            keys.append(self._current.key)
        return keys

    def can_go_back(self) -> bool:
        return bool(self._stack)

    def at_home(self) -> bool:
        return self.current == self.home and not self._stack

    # ---- navigation ------------------------------------------------------

    def _resolve(self, key: str) -> Route:
        route = self._routes.get(key)
        if route is None or route.render is None:
            raise RouteDenied(f"route not registered: {key}")
        if self.can_render is not None and not self.can_render(route):
            raise RouteDenied(f"no permission for route: {key}")
        return route

    def _leave_current(self, next_route: Route) -> None:
        prev = self._current
        if prev is not None and prev.key != next_route.key and prev.on_leave is not None:
            try:
                prev.on_leave(prev.key, dict(self._current_kwargs))
            except Exception:
                pass

    def _enter(self, route: Route, kwargs: dict) -> bool:
        assert self.render is not None
        self.render(route.key, kwargs)
        self._current = route
        self._current_kwargs = dict(kwargs)
        if self.on_change is not None:
            self.on_change(route)
        return True

    def _denied(self, exc: Exception, key: str, kwargs: dict) -> bool:
        if self.on_denied is not None:
            self.on_denied(exc, key, dict(kwargs))
        return False

    def go(self, key: str, *, reset: bool = False, replace: bool = False, **kwargs) -> bool:
        """Navigate to ``key``.

        * default          -> push the current entry onto the back-stack.
        * ``reset=True``   -> clear the back-stack first (tab-bar taps).
        * ``replace=True`` -> swap the current entry without pushing.

        Returns True when the route rendered, False when denied.
        """
        try:
            route = self._resolve(key)
        except RouteDenied as exc:
            return self._denied(exc, key, kwargs)
        if self.render is None:
            return self._denied(RouteDenied("router has no render callback"), key, kwargs)

        pushed = False
        if reset:
            self._stack.clear()
        elif self._current is not None:
            if replace:
                pass
            elif route.replace_current and self._current.key == key:
                pass
            else:
                self._stack.append((self._current.key, dict(self._current_kwargs)))
                pushed = True
        try:
            self._leave_current(route)
            return self._enter(route, kwargs)
        except Exception:
            if pushed:
                self._stack.pop()
            return False

    def back(self) -> bool:
        """Pop the back-stack and re-render the previous entry.

        Returns False when already at the root of the stack."""
        if not self._stack:
            return False
        key, kwargs = self._stack.pop()
        try:
            route = self._resolve(key)
        except RouteDenied:
            self._stack.clear()
            try:
                return self._enter(self._resolve(self.home), {})
            except Exception as home_exc:
                return self._denied(home_exc, self.home, {})
        self._leave_current(route)
        return self._enter(route, kwargs)

    def reset_to(self, key: str, **kwargs) -> bool:
        """Hard reset: clears the stack and re-renders ``key`` as the root."""
        self._stack.clear()
        return self.go(key, reset=True, **kwargs)
