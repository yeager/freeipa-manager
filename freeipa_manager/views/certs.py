"""Certificates view — list certs, track expiry, show warnings."""

import gettext
import logging
import threading
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

from ..widgets.export import export_dialog  # noqa: E402
from ..widgets.search import SearchBar  # noqa: E402

_ = gettext.gettext
log = logging.getLogger(__name__)


class CertObject(GObject.Object):
    """GObject wrapper for a certificate record."""

    serial = GObject.Property(type=str, default="")
    subject = GObject.Property(type=str, default="")
    status = GObject.Property(type=str, default="")
    not_after = GObject.Property(type=str, default="")
    days_remaining = GObject.Property(type=str, default="")

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self.serial = str(data.get("serial_number", ""))
        subj = data.get("subject", "")
        if isinstance(subj, dict):
            self.subject = subj.get("CN", str(subj))
        elif isinstance(subj, str):
            self.subject = subj
        else:
            self.subject = str(subj)

        self.status = str(data.get("status", ""))
        self.not_after = str(data.get("valid_not_after", ""))

        # Calculate days remaining
        not_after_val = data.get("valid_not_after")
        if isinstance(not_after_val, str):
            try:
                exp = datetime.fromisoformat(not_after_val.replace("Z", "+00:00"))
                remaining = (exp - datetime.now(tz=timezone.utc)).days
                self.days_remaining = str(remaining)
            except ValueError:
                self.days_remaining = "?"
        else:
            self.days_remaining = "?"


class CertsView(Gtk.Box):
    """Certificate management view."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self._certs_data: list[dict] = []

        self._search = SearchBar(placeholder=_("Search certificates…"))
        self._search.connect_changed(self._on_search_changed)
        self.append(self._search)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        self._expiring_btn = Gtk.ToggleButton(label=_("Expiring Only"))
        self._expiring_btn.connect("toggled", self._on_filter_expiring)
        toolbar.append(self._expiring_btn)

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
        self._store = Gio.ListStore.new(CertObject)
        self._filter_model = Gtk.FilterListModel.new(self._store, None)
        self._selection = Gtk.SingleSelection.new(self._filter_model)
        self._selection.connect("notify::selected-item", self._on_cert_selected)

        self._column_view = Gtk.ColumnView.new(self._selection)
        self._column_view.add_css_class("data-table")
        self._column_view.set_show_column_separators(True)

        columns = [
            (_("Serial"), "serial", 120),
            (_("Subject"), "subject", 250),
            (_("Status"), "status", 100),
            (_("Expires"), "not_after", 180),
            (_("Days Left"), "days_remaining", 80),
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
                Gtk.PropertyExpression.new(CertObject, None, "subject")
            )
            string_filter.set_search(text)
            string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
            self._filter_model.set_filter(string_filter)
        else:
            self._filter_model.set_filter(None)

    def _on_filter_expiring(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            # Show only certs expiring within 90 days
            self._store.remove_all()
            for data in self._certs_data:
                obj = CertObject(data)
                try:
                    if obj.days_remaining != "?" and int(obj.days_remaining) <= 90:
                        self._store.append(obj)
                except ValueError:
                    pass
        else:
            self._store.remove_all()
            for data in self._certs_data:
                self._store.append(CertObject(data))

    def _on_cert_selected(self, selection: Gtk.SingleSelection,
                          _pspec: object) -> None:
        item = selection.get_selected_item()
        if not item:
            return

        lines = [
            _("Serial: %s") % item.serial,
            _("Subject: %s") % item.subject,
            _("Status: %s") % item.status,
            _("Expires: %s") % item.not_after,
            _("Days Remaining: %s") % item.days_remaining,
        ]

        dialog = Adw.AlertDialog.new(
            _("Certificate Details"),
            "\n".join(lines),
        )
        dialog.add_response("close", _("Close"))
        dialog.present(self.window)

    def _on_export(self, _btn: Gtk.Button) -> None:
        columns = ["serial_number", "subject", "status", "valid_not_after"]
        export_dialog(self.window, self._certs_data, columns)

    def refresh(self) -> None:
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> list | str:
            try:
                result = client.cert_find(sizelimit=0)
                return result.get("result", [])
            except Exception as exc:
                return str(exc)

        def on_done(result: list | str) -> None:
            if isinstance(result, str):
                log.error("Cert fetch failed: %s", result)
                return
            self._certs_data = result
            self._store.remove_all()
            for data in result:
                self._store.append(CertObject(data))
            self._count_label.set_text(_("%d certificates") % len(result))

            # Check for expiring certs and send notification
            self._check_expiry_notifications(result)

        def thread_target() -> None:
            r = fetch()
            GLib.idle_add(on_done, r)

        threading.Thread(target=thread_target, daemon=True).start()

    def _check_expiry_notifications(self, certs: list) -> None:
        """Send desktop notification for expiring certificates."""
        now = datetime.now(tz=timezone.utc)
        critical = []

        for cert in certs:
            not_after = cert.get("valid_not_after")
            if isinstance(not_after, str):
                try:
                    exp = datetime.fromisoformat(not_after.replace("Z", "+00:00"))
                    remaining = (exp - now).days
                    if remaining <= 30:
                        subj = cert.get("subject", "")
                        if isinstance(subj, dict):
                            subj = subj.get("CN", str(subj))
                        critical.append((str(subj), remaining))
                except ValueError:
                    pass

        if critical and self.window:
            app = self.window.get_application()
            if app:
                notif = Gio.Notification.new(
                    _("Certificate Expiry Warning")
                )
                notif.set_body(
                    _("%d certificate(s) expiring within 30 days") % len(critical)
                )
                notif.set_priority(Gio.NotificationPriority.HIGH)
                app.send_notification("cert-expiry", notif)
