"""Reusable search bar widget."""

import gettext
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

_ = gettext.gettext


class SearchBar(Gtk.Box):
    """A search entry bar with debounced change notifications."""

    def __init__(self, placeholder: str = "", **kwargs) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            **kwargs,
        )
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(4)

        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text(placeholder or _("Search…"))
        self._entry.set_hexpand(True)
        self.append(self._entry)

        self._callbacks: list[Callable[[str], None]] = []
        self._entry.connect("search-changed", self._on_changed)

    def connect_changed(self, callback: Callable[[str], None]) -> None:
        """Register a callback for search text changes."""
        self._callbacks.append(callback)

    def _on_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text()
        for cb in self._callbacks:
            cb(text)

    def grab_focus(self) -> bool:
        return self._entry.grab_focus()

    def get_text(self) -> str:
        return self._entry.get_text()
