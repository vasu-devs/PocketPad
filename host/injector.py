"""Input injector abstraction.

`Injector` is the interface the server depends on. `WindowsInjector` (in
`input_win.py`) is the real implementation built on SendInput. `FakeInjector`
records calls and is used by tests.
"""
from __future__ import annotations

from typing import Iterable, Protocol


class Injector(Protocol):
    def move(self, dx: int, dy: int) -> None: ...
    def button(self, button: str, down: bool) -> None: ...
    def wheel(self, delta: int, horizontal: bool = False) -> None: ...
    def key_combo(self, keys: Iterable[str]) -> None: ...
    def key(self, key: str, down: bool) -> None: ...
    def type_text(self, text: str) -> None: ...


class FakeInjector:
    """Records every call; used in unit tests and `--dry-run` mode."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def move(self, dx: int, dy: int) -> None:
        self.calls.append(("move", dx, dy))

    def button(self, button: str, down: bool) -> None:
        self.calls.append(("button", button, down))

    def wheel(self, delta: int, horizontal: bool = False) -> None:
        self.calls.append(("wheel", delta, horizontal))

    def key_combo(self, keys: Iterable[str]) -> None:
        self.calls.append(("combo", tuple(keys)))

    def key(self, key: str, down: bool) -> None:
        self.calls.append(("key", key, down))

    def type_text(self, text: str) -> None:
        self.calls.append(("text", text))
