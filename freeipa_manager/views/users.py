"""Users view — list, search, create, edit, disable/enable users."""

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


class UserObject(GObject.Object):
    """GObject wrapper for a user record."""

    uid = GObject.Property(type=str, default="")
    givenname = GObject.Property(type=str, default="")
    sn = GObject.Property(type=str, default="")
    mail = GObject.Property(type=str, default="")
    disabled = GObject.Property(type=str, default="")

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self.uid = self._first(data.get("uid", ""))
        self.givenname = self._first(data.get("givenname", ""))
        self.sn = self._first(data.get("sn", ""))
        self.mail = self._first(data.get("mail", ""))
        locked = data.get("nsaccountlock", False)
        if isinstance(locked, list):
            locked = locked[0] if locked else False
        self.disabled = _("Yes") if locked in (True, "TRUE", "True") else _("No")

    @staticmethod
    def _first(val: object) -> str:
        if isinstance(val, list):
            return str(val[0]) if val else ""
        return str(val) if val else ""


class UsersView(Gtk.Box):
    """User management view with column view and detail panel."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self._users_data: list[dict] = []

        # Search bar
        self._search = SearchBar(placeholder=_("Search users…"))
        self._search.connect_changed(self._on_search_changed)
        self.append(self._search)

        # Toolbar with actions
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        add_btn = Gtk.Button(label=_("Add User"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_user)
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

        # Model and column view
        self._store = Gio.ListStore.new(UserObject)
        self._filter_model = Gtk.FilterListModel.new(self._store, None)
        self._selection = Gtk.SingleSelection.new(self._filter_model)
        self._selection.connect("notify::selected-item", self._on_user_selected)

        self._column_view = Gtk.ColumnView.new(self._selection)
        self._column_view.add_css_class("data-table")
        self._column_view.set_show_column_separators(True)

        columns = [
            (_("Login"), "uid", 140),
            (_("First Name"), "givenname", 140),
            (_("Last Name"), "sn", 140),
            (_("Email"), "mail", 200),
            (_("Disabled"), "disabled", 80),
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
                Gtk.PropertyExpression.new(UserObject, None, "uid")
            )
            string_filter.set_search(text)
            string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
            self._filter_model.set_filter(string_filter)
        else:
            self._filter_model.set_filter(None)

    def _on_user_selected(self, selection: Gtk.SingleSelection,
                          _pspec: object) -> None:
        item = selection.get_selected_item()
        if item and self.window and self.window.client:
            self._show_user_detail(item.uid)

    def _show_user_detail(self, uid: str) -> None:
        """Show user detail dialog."""
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> dict | str:
            try:
                result = client.user_show(uid, all=True)
                return result.get("result", {})
            except Exception as exc:
                return str(exc)

        def on_done(result: dict | str) -> None:
            if isinstance(result, str):
                return
            self._present_detail_dialog(result)

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()

    def _present_detail_dialog(self, user: dict) -> None:
        uid = user.get("uid", [""])[0] if isinstance(user.get("uid"), list) else user.get("uid", "")
        cn = user.get("cn", [""])[0] if isinstance(user.get("cn"), list) else user.get("cn", "")

        dialog = Adw.AlertDialog.new(cn or uid, "")

        fields = [
            (_("Login"), "uid"),
            (_("First Name"), "givenname"),
            (_("Last Name"), "sn"),
            (_("Email"), "mail"),
            (_("UID Number"), "uidnumber"),
            (_("GID Number"), "gidnumber"),
            (_("Home Directory"), "homedirectory"),
            (_("Shell"), "loginshell"),
        ]
        lines = []
        for label, key in fields:
            val = user.get(key, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            lines.append(f"{label}: {val}")

        dialog.set_body("\n".join(lines))
        dialog.add_response("close", _("Close"))
        dialog.add_response("edit", _("Edit"))
        dialog.set_response_appearance("edit", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_detail_response, uid)
        dialog.present(self.window)

    def _on_detail_response(self, dialog: Adw.AlertDialog, response: str,
                            uid: str) -> None:
        if response == "edit":
            self._show_edit_dialog(uid)

    def _show_edit_dialog(self, uid: str) -> None:
        """Show edit user dialog."""
        dialog = Adw.AlertDialog.new(
            _("Edit User: %s") % uid,
            _("Editing is performed via FreeIPA API calls."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("disable", _("Disable"))
        dialog.add_response("enable", _("Enable"))
        dialog.set_response_appearance("disable", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("enable", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_edit_response, uid)
        dialog.present(self.window)

    def _on_edit_response(self, dialog: Adw.AlertDialog, response: str,
                          uid: str) -> None:
        if response not in ("disable", "enable"):
            return
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def do_action() -> str | None:
            try:
                if response == "disable":
                    client.user_disable(uid)
                else:
                    client.user_enable(uid)
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
            error = do_action()
            GLib.idle_add(on_done, error)

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_add_user(self, _btn: Gtk.Button) -> None:
        """Show add user dialog."""
        dialog = Adw.AlertDialog.new(_("Add User"), "")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        entries = {}
        for label, key in [(_("Login"), "uid"), (_("First Name"), "givenname"),
                           (_("Last Name"), "sn")]:
            row = Adw.EntryRow()
            row.set_title(label)
            entries[key] = row
            box.append(row)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_add_response, entries)
        dialog.present(self.window)

    def _on_add_response(self, dialog: Adw.AlertDialog, response: str,
                         entries: dict) -> None:
        if response != "create":
            return
        if not self.window or not self.window.client:
            return

        uid = entries["uid"].get_text().strip()
        givenname = entries["givenname"].get_text().strip()
        sn = entries["sn"].get_text().strip()

        if not uid or not givenname or not sn:
            err = Adw.AlertDialog.new(_("Error"), _("All fields are required."))
            err.add_response("ok", _("OK"))
            err.present(self.window)
            return

        client = self.window.client

        def do_add() -> str | None:
            try:
                client.user_add(uid, givenname=givenname, sn=sn)
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

    def _on_export(self, _btn: Gtk.Button) -> None:
        columns = ["uid", "givenname", "sn", "mail", "nsaccountlock"]
        export_dialog(self.window, self._users_data, columns)

    def refresh(self) -> None:
        """Fetch users from the server."""
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> list | str:
            try:
                result = client.user_find(sizelimit=0)
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("User fetch failed: %s", result)
                return
            self._users_data = result
            self._store.remove_all()
            for user_data in result:
                self._store.append(UserObject(user_data))
            self._count_label.set_text(_("%d users") % len(result))

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()
