"""Groups view — list, search, create groups and manage members."""

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


class GroupObject(GObject.Object):
    """GObject wrapper for a group record."""

    cn = GObject.Property(type=str, default="")
    description = GObject.Property(type=str, default="")
    gidnumber = GObject.Property(type=str, default="")
    member_count = GObject.Property(type=str, default="")

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self.cn = self._first(data.get("cn", ""))
        self.description = self._first(data.get("description", ""))
        self.gidnumber = self._first(data.get("gidnumber", ""))
        members = data.get("member_user", data.get("member", []))
        self.member_count = str(len(members)) if isinstance(members, list) else "0"

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""


class GroupsView(Gtk.Box):
    """Group management view."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self._groups_data: list[dict] = []

        # Search bar
        self._search = SearchBar(placeholder=_("Search groups…"))
        self._search.connect_changed(self._on_search_changed)
        self.append(self._search)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        add_btn = Gtk.Button(label=_("Add Group"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_group)
        toolbar.append(add_btn)

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

        # Column view
        self._store = Gio.ListStore.new(GroupObject)
        self._filter_model = Gtk.FilterListModel.new(self._store, None)
        self._selection = Gtk.SingleSelection.new(self._filter_model)
        self._selection.connect("notify::selected-item", self._on_group_selected)

        self._column_view = Gtk.ColumnView.new(self._selection)
        self._column_view.add_css_class("data-table")
        self._column_view.set_show_column_separators(True)

        columns = [
            (_("Name"), "cn", 200),
            (_("Description"), "description", 300),
            (_("GID"), "gidnumber", 100),
            (_("Members"), "member_count", 80),
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
                Gtk.PropertyExpression.new(GroupObject, None, "cn")
            )
            string_filter.set_search(text)
            string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
            self._filter_model.set_filter(string_filter)
        else:
            self._filter_model.set_filter(None)

    def _on_group_selected(self, selection: Gtk.SingleSelection,
                           _pspec: object) -> None:
        item = selection.get_selected_item()
        if item and self.window and self.window.client:
            self._show_group_detail(item.cn)

    def _show_group_detail(self, cn: str) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> dict | str:
            try:
                result = client.group_show(cn, all=True)
                return result.get("result", {})
            except Exception as exc:
                return str(exc)

        def on_done(result: dict | str) -> None:
            if isinstance(result, str):
                return

            group_cn = result.get("cn", [""])[0] if isinstance(result.get("cn"), list) else result.get("cn", "")
            desc = result.get("description", [""])[0] if isinstance(result.get("description"), list) else result.get("description", "")
            members = result.get("member_user", [])
            if isinstance(members, list):
                members_str = ", ".join(str(m) for m in members) or _("None")
            else:
                members_str = str(members)

            dialog = Adw.AlertDialog.new(
                group_cn,
                _("Description: %s\nGID: %s\nMembers: %s") % (
                    desc,
                    self._first(result.get("gidnumber", "")),
                    members_str,
                ),
            )
            dialog.add_response("close", _("Close"))
            dialog.add_response("add_member", _("Add Member"))
            dialog.set_response_appearance("add_member", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", self._on_detail_response, group_cn)
            dialog.present(self.window)

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_detail_response(self, dialog: Adw.AlertDialog, response: str,
                            cn: str) -> None:
        if response == "add_member":
            self._show_add_member_dialog(cn)

    def _show_add_member_dialog(self, cn: str) -> None:
        dialog = Adw.AlertDialog.new(_("Add Member to %s") % cn, "")
        entry = Adw.EntryRow()
        entry.set_title(_("User Login"))
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_add_member_response, cn, entry)
        dialog.present(self.window)

    def _on_add_member_response(self, dialog: Adw.AlertDialog, response: str,
                                cn: str, entry: Adw.EntryRow) -> None:
        if response != "add":
            return
        uid = entry.get_text().strip()
        if not uid or not self.window or not self.window.client:
            return

        client = self.window.client

        def do_add() -> str | None:
            try:
                client.group_add_member(cn, user=uid)
                return None
            except Exception as exc:
                return str(exc)

        def on_done(error: str | None) -> None:
            if error:
                err_dialog = Adw.AlertDialog.new(_("Error"), str(error))
                err_dialog.add_response("ok", _("OK"))
                err_dialog.present(self.window)
            else:
                self.refresh()

        def thread_target() -> None:
            error = do_add()
            GLib.idle_add(on_done, error)

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_add_group(self, _btn: Gtk.Button) -> None:
        dialog = Adw.AlertDialog.new(_("Add Group"), "")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        cn_entry = Adw.EntryRow()
        cn_entry.set_title(_("Group Name"))
        box.append(cn_entry)

        desc_entry = Adw.EntryRow()
        desc_entry.set_title(_("Description"))
        box.append(desc_entry)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_add_group_response, cn_entry, desc_entry)
        dialog.present(self.window)

    def _on_add_group_response(self, dialog: Adw.AlertDialog, response: str,
                               cn_entry: Adw.EntryRow,
                               desc_entry: Adw.EntryRow) -> None:
        if response != "create":
            return
        # Placeholder: would call group_add API
        self.refresh()

    def _on_export(self, _btn: Gtk.Button) -> None:
        columns = ["cn", "description", "gidnumber"]
        export_dialog(self.window, self._groups_data, columns)

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""

    def refresh(self) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> list | str:
            try:
                result = client.group_find(sizelimit=0)
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("Group fetch failed: %s", result)
                return
            self._groups_data = result
            self._store.remove_all()
            for data in result:
                self._store.append(GroupObject(data))
            self._count_label.set_text(_("%d groups") % len(result))

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()
