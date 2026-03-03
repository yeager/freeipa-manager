"""DNS view — zones and records."""

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


class ZoneObject(GObject.Object):
    """GObject wrapper for a DNS zone."""

    idnsname = GObject.Property(type=str, default="")
    active = GObject.Property(type=str, default="")

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self.idnsname = self._first(data.get("idnsname", ""))
        active = data.get("idnszoneactive", "")
        if isinstance(active, list):
            active = active[0] if active else ""
        self.active = _("Yes") if active in (True, "TRUE", "True") else _("No")

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""


class RecordObject(GObject.Object):
    """GObject wrapper for a DNS record."""

    idnsname = GObject.Property(type=str, default="")
    record_type = GObject.Property(type=str, default="")
    record_data = GObject.Property(type=str, default="")

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self.idnsname = self._first(data.get("idnsname", ""))

        # Determine record type and data
        for rtype in ("arecord", "aaaarecord", "cnamerecord", "mxrecord",
                      "txtrecord", "srvrecord", "ptrrecord", "nsrecord"):
            val = data.get(rtype)
            if val:
                self.record_type = rtype.replace("record", "").upper()
                if isinstance(val, list):
                    self.record_data = ", ".join(str(v) for v in val)
                else:
                    self.record_data = str(val)
                break

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""


class DNSView(Gtk.Box):
    """DNS management view — zones and records."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self._dns_data: list[dict] = []
        self._selected_zone: str | None = None
        self._showing_records = False

        self._search = SearchBar(placeholder=_("Search DNS…"))
        self._search.connect_changed(self._on_search_changed)
        self.append(self._search)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        self._back_btn = Gtk.Button(label=_("← Zones"))
        self._back_btn.connect("clicked", self._on_back_to_zones)
        self._back_btn.set_visible(False)
        toolbar.append(self._back_btn)

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

        # Stack for zones vs records view
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Zones column view
        self._zone_store = Gio.ListStore.new(ZoneObject)
        self._zone_filter = Gtk.FilterListModel.new(self._zone_store, None)
        zone_selection = Gtk.SingleSelection.new(self._zone_filter)
        zone_selection.connect("notify::selected-item", self._on_zone_selected)

        zone_cv = Gtk.ColumnView.new(zone_selection)
        zone_cv.add_css_class("data-table")
        zone_cv.set_show_column_separators(True)

        for title, attr, width in [(_("Zone"), "idnsname", 300), (_("Active"), "active", 80)]:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_col_setup)
            factory.connect("bind", self._on_col_bind, attr)
            col = Gtk.ColumnViewColumn.new(title, factory)
            col.set_resizable(True)
            col.set_fixed_width(width)
            zone_cv.append_column(col)

        zone_scroll = Gtk.ScrolledWindow()
        zone_scroll.set_child(zone_cv)
        zone_scroll.set_vexpand(True)
        self._stack.add_named(zone_scroll, "zones")

        # Records column view
        self._record_store = Gio.ListStore.new(RecordObject)
        self._record_filter = Gtk.FilterListModel.new(self._record_store, None)
        record_selection = Gtk.SingleSelection.new(self._record_filter)
        record_selection.connect("notify::selected-item", self._on_record_selected)

        record_cv = Gtk.ColumnView.new(record_selection)
        record_cv.add_css_class("data-table")
        record_cv.set_show_column_separators(True)

        for title, attr, width in [(_("Name"), "idnsname", 200),
                                    (_("Type"), "record_type", 80),
                                    (_("Data"), "record_data", 300)]:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_col_setup)
            factory.connect("bind", self._on_col_bind, attr)
            col = Gtk.ColumnViewColumn.new(title, factory)
            col.set_resizable(True)
            col.set_fixed_width(width)
            record_cv.append_column(col)

        record_scroll = Gtk.ScrolledWindow()
        record_scroll.set_child(record_cv)
        record_scroll.set_vexpand(True)
        self._stack.add_named(record_scroll, "records")

        self._stack.set_visible_child_name("zones")
        self.append(self._stack)

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
        if self._showing_records:
            if text:
                string_filter = Gtk.StringFilter.new(
                    Gtk.PropertyExpression.new(RecordObject, None, "idnsname")
                )
                string_filter.set_search(text)
                string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
                self._record_filter.set_filter(string_filter)
            else:
                self._record_filter.set_filter(None)
        else:
            if text:
                string_filter = Gtk.StringFilter.new(
                    Gtk.PropertyExpression.new(ZoneObject, None, "idnsname")
                )
                string_filter.set_search(text)
                string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
                self._zone_filter.set_filter(string_filter)
            else:
                self._zone_filter.set_filter(None)

    def _on_zone_selected(self, selection: Gtk.SingleSelection,
                          _pspec: object) -> None:
        item = selection.get_selected_item()
        if item:
            self._selected_zone = item.idnsname
            self._load_records(item.idnsname)

    def _on_record_selected(self, selection: Gtk.SingleSelection,
                            _pspec: object) -> None:
        item = selection.get_selected_item()
        if not item:
            return
        dialog = Adw.AlertDialog.new(
            item.idnsname,
            _("Type: %s\nData: %s") % (item.record_type, item.record_data),
        )
        dialog.add_response("close", _("Close"))
        dialog.present(self.window)

    def _on_back_to_zones(self, _btn: Gtk.Button) -> None:
        self._showing_records = False
        self._back_btn.set_visible(False)
        self._stack.set_visible_child_name("zones")

    def _load_records(self, zone: str) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> list | str:
            try:
                result = client.dnsrecord_find(zone)
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("DNS record fetch failed: %s", result)
                return
            self._dns_data = result
            self._record_store.remove_all()
            for data in result:
                self._record_store.append(RecordObject(data))
            self._count_label.set_text(_("%d records") % len(result))
            self._showing_records = True
            self._back_btn.set_visible(True)
            self._stack.set_visible_child_name("records")

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_export(self, _btn: Gtk.Button) -> None:
        if self._showing_records:
            columns = ["idnsname", "arecord", "cnamerecord"]
        else:
            columns = ["idnsname", "idnszoneactive"]
        export_dialog(self.window, self._dns_data, columns)

    def refresh(self) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> list | str:
            try:
                result = client.dnszone_find()
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("DNS zone fetch failed: %s", result)
                return
            self._dns_data = result
            self._zone_store.remove_all()
            for data in result:
                self._zone_store.append(ZoneObject(data))
            self._count_label.set_text(_("%d zones") % len(result))
            self._showing_records = False
            self._back_btn.set_visible(False)
            self._stack.set_visible_child_name("zones")

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()
