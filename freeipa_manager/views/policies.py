"""Policies view — HBAC and sudo rules."""

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


class PolicyObject(GObject.Object):
    """GObject wrapper for an HBAC or sudo rule."""

    cn = GObject.Property(type=str, default="")
    enabled = GObject.Property(type=str, default="")
    description = GObject.Property(type=str, default="")
    policy_type = GObject.Property(type=str, default="")

    def __init__(self, data: dict, ptype: str = "HBAC") -> None:
        super().__init__()
        self._data = data
        self.cn = self._first(data.get("cn", ""))
        enabled = data.get("ipaenabledflag", "")
        if isinstance(enabled, list):
            enabled = enabled[0] if enabled else ""
        self.enabled = _("Yes") if enabled in (True, "TRUE", "True") else _("No")
        self.description = self._first(data.get("description", ""))
        self.policy_type = ptype

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""


class PoliciesView(Gtk.Box):
    """Policies view with HBAC/sudo toggle."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self._policies_data: list[dict] = []
        self._current_type = "hbac"

        self._search = SearchBar(placeholder=_("Search policies…"))
        self._search.connect_changed(self._on_search_changed)
        self.append(self._search)

        # Toggle bar for HBAC / Sudo
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toggle_box.set_margin_start(8)
        toggle_box.set_margin_end(8)
        toggle_box.set_margin_top(4)
        toggle_box.set_margin_bottom(4)

        self._hbac_btn = Gtk.ToggleButton(label=_("HBAC Rules"))
        self._hbac_btn.set_active(True)
        self._hbac_btn.connect("toggled", self._on_type_toggled, "hbac")
        toggle_box.append(self._hbac_btn)

        self._sudo_btn = Gtk.ToggleButton(label=_("Sudo Rules"))
        self._sudo_btn.set_group(self._hbac_btn)
        self._sudo_btn.connect("toggled", self._on_type_toggled, "sudo")
        toggle_box.append(self._sudo_btn)

        export_btn = Gtk.Button(label=_("Export"))
        export_btn.connect("clicked", self._on_export)
        toggle_box.append(export_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toggle_box.append(spacer)

        self._count_label = Gtk.Label(label="")
        self._count_label.add_css_class("dim-label")
        toggle_box.append(self._count_label)

        self.append(toggle_box)

        # Column view
        self._store = Gio.ListStore.new(PolicyObject)
        self._filter_model = Gtk.FilterListModel.new(self._store, None)
        self._selection = Gtk.SingleSelection.new(self._filter_model)
        self._selection.connect("notify::selected-item", self._on_policy_selected)

        self._column_view = Gtk.ColumnView.new(self._selection)
        self._column_view.add_css_class("data-table")
        self._column_view.set_show_column_separators(True)

        columns = [
            (_("Name"), "cn", 200),
            (_("Type"), "policy_type", 80),
            (_("Enabled"), "enabled", 80),
            (_("Description"), "description", 300),
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
                Gtk.PropertyExpression.new(PolicyObject, None, "cn")
            )
            string_filter.set_search(text)
            string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
            self._filter_model.set_filter(string_filter)
        else:
            self._filter_model.set_filter(None)

    def _on_type_toggled(self, btn: Gtk.ToggleButton, ptype: str) -> None:
        if btn.get_active():
            self._current_type = ptype
            self.refresh()

    def _on_policy_selected(self, selection: Gtk.SingleSelection,
                            _pspec: object) -> None:
        item = selection.get_selected_item()
        if not item:
            return

        lines = [
            _("Name: %s") % item.cn,
            _("Type: %s") % item.policy_type,
            _("Enabled: %s") % item.enabled,
            _("Description: %s") % item.description,
        ]

        dialog = Adw.AlertDialog.new(item.cn, "\n".join(lines))
        dialog.add_response("close", _("Close"))
        dialog.present(self.window)

    def _on_export(self, _btn: Gtk.Button) -> None:
        columns = ["cn", "ipaenabledflag", "description"]
        export_dialog(self.window, self._policies_data, columns)

    def refresh(self) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client
        ptype = self._current_type

        def fetch() -> list | str:
            try:
                if ptype == "sudo":
                    result = client.sudorule_find(sizelimit=0)
                else:
                    result = client.hbacrule_find(sizelimit=0)
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("Policy fetch failed: %s", result)
                return
            self._policies_data = result
            label = "HBAC" if ptype == "hbac" else "Sudo"
            self._store.remove_all()
            for data in result:
                self._store.append(PolicyObject(data, label))
            self._count_label.set_text(_("%d rules") % len(result))

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()
