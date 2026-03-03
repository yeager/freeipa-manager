"""Hosts view — list registered hosts and enrollment status."""

import gettext
import logging
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

from ..widgets.export import export_dialog  # noqa: E402
from ..widgets.search import SearchBar  # noqa: E402

_ = gettext.gettext
log = logging.getLogger(__name__)


class HostObject(GObject.Object):
    """GObject wrapper for a host record."""

    fqdn = GObject.Property(type=str, default="")
    description = GObject.Property(type=str, default="")
    has_keytab = GObject.Property(type=str, default="")
    managedby = GObject.Property(type=str, default="")

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self.fqdn = self._first(data.get("fqdn", ""))
        self.description = self._first(data.get("description", ""))
        kt = data.get("has_keytab", False)
        if isinstance(kt, list):
            kt = kt[0] if kt else False
        self.has_keytab = _("Yes") if kt in (True, "TRUE", "True") else _("No")
        managed = data.get("managedby_host", [])
        if isinstance(managed, list):
            self.managedby = ", ".join(str(m) for m in managed)
        else:
            self.managedby = str(managed) if managed else ""

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""


class HostsView(Gtk.Box):
    """Host management view."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self._hosts_data: list[dict] = []

        self._search = SearchBar(placeholder=_("Search hosts…"))
        self._search.connect_changed(self._on_search_changed)
        self.append(self._search)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        export_btn = Gtk.Button(label=_("Export"))
        export_btn.connect("clicked", self._on_export)
        toolbar.append(export_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        self._count_label = Gtk.Label(label="")
        self._count_label.add_css_class("dim-label")
        toolbar.append(self._count_label)

        self.append(toolbar)

        self._store = Gio.ListStore.new(HostObject)
        self._filter_model = Gtk.FilterListModel.new(self._store, None)
        self._selection = Gtk.SingleSelection.new(self._filter_model)
        self._selection.connect("notify::selected-item", self._on_host_selected)

        self._column_view = Gtk.ColumnView.new(self._selection)
        self._column_view.add_css_class("data-table")
        self._column_view.set_show_column_separators(True)

        columns = [
            (_("FQDN"), "fqdn", 280),
            (_("Description"), "description", 200),
            (_("Enrolled"), "has_keytab", 80),
            (_("Managed By"), "managedby", 200),
        ]
        for title, attr, width in columns:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_col_setup)
            factory.connect("bind", self._on_col_bind, attr)
            col = Gtk.ColumnViewColumn.new(title, factory)
            col.set_resizable(True)
            col.set_fixed_width(width)
            self._column_view.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._column_view)
        scrolled.set_vexpand(True)
        self.append(scrolled)

    def focus_search(self) -> None:
        self._search.grab_focus()

    @staticmethod
    def _on_col_setup(factory: Gtk.SignalListItemFactory,
                      list_item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(3)
        label.set_margin_start(8)
        label.set_margin_end(8)
        list_item.set_child(label)

    @staticmethod
    def _on_col_bind(factory: Gtk.SignalListItemFactory,
                     list_item: Gtk.ListItem, attr: str) -> None:
        item = list_item.get_item()
        label = list_item.get_child()
        label.set_text(getattr(item, attr, ""))

    def _on_search_changed(self, text: str) -> None:
        if text:
            string_filter = Gtk.StringFilter.new(
                Gtk.PropertyExpression.new(HostObject, None, "fqdn")
            )
            string_filter.set_search(text)
            string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
            self._filter_model.set_filter(string_filter)
        else:
            self._filter_model.set_filter(None)

    def _on_host_selected(self, selection: Gtk.SingleSelection,
                          _pspec: object) -> None:
        item = selection.get_selected_item()
        if item and self.window and self.window.client:
            self._show_host_detail(item.fqdn)

    def _show_host_detail(self, fqdn: str) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> dict | str:
            try:
                result = client.host_show(fqdn, all=True)
                return result.get("result", {})
            except Exception as exc:
                return str(exc)

        def on_done(result: dict | str) -> None:
            if isinstance(result, str):
                return
            host_fqdn = result.get("fqdn", [""])[0] if isinstance(result.get("fqdn"), list) else result.get("fqdn", "")
            fields = [
                (_("FQDN"), "fqdn"),
                (_("Description"), "description"),
                (_("Platform"), "nshardwareplatform"),
                (_("OS"), "nsosversion"),
                (_("Enrolled"), "has_keytab"),
            ]
            lines = []
            for label, key in fields:
                val = result.get(key, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                lines.append(f"{label}: {val}")

            dialog = Adw.AlertDialog.new(host_fqdn, "\n".join(lines))
            dialog.add_response("close", _("Close"))
            dialog.present(self.window)

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_export(self, _btn: Gtk.Button) -> None:
        columns = ["fqdn", "description", "has_keytab"]
        export_dialog(self.window, self._hosts_data, columns)

    def refresh(self) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> list | str:
            try:
                result = client.host_find(sizelimit=0)
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("Host fetch failed: %s", result)
                return
            self._hosts_data = result
            self._store.remove_all()
            for data in result:
                self._store.append(HostObject(data))
            self._count_label.set_text(_("%d hosts") % len(result))

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()
