"""Dashboard view — overview cards, cert warnings, replication status."""

import gettext
import logging
import threading
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

_ = gettext.gettext
log = logging.getLogger(__name__)


class StatCard(Gtk.Frame):
    """A card displaying a statistic with title and value."""

    def __init__(self, title: str, value: str = "—", icon: str = "") -> None:
        super().__init__()
        self.add_css_class("card")
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_halign(Gtk.Align.CENTER)

        if icon:
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(32)
            img.add_css_class("dim-label")
            box.append(img)

        self._value_label = Gtk.Label(label=value)
        self._value_label.add_css_class("title-1")
        box.append(self._value_label)

        title_label = Gtk.Label(label=title)
        title_label.add_css_class("dim-label")
        box.append(title_label)

        self.set_child(box)

    def set_value(self, value: str) -> None:
        self._value_label.set_text(value)


class CertWarningRow(Gtk.Box):
    """A row showing a certificate expiry warning."""

    def __init__(self, subject: str, days: int) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        if days <= 30:
            icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
            icon.add_css_class("error")
        else:
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("warning")
        self.append(icon)

        label = Gtk.Label(label=subject, hexpand=True, xalign=0)
        label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        self.append(label)

        days_label = Gtk.Label(label=_("%d days") % days)
        if days <= 30:
            days_label.add_css_class("error")
        else:
            days_label.add_css_class("warning")
        self.append(days_label)


class DashboardView(Gtk.Box):
    """Dashboard overview with stats, cert warnings, and replication status."""

    def __init__(self, window: "FreeIPAWindow" = None, **kwargs) -> None:  # noqa: F821
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)

        # -- Stats cards --
        cards_label = Gtk.Label(label=_("Overview"), xalign=0)
        cards_label.add_css_class("title-2")
        content.append(cards_label)

        cards_grid = Gtk.FlowBox()
        cards_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        cards_grid.set_max_children_per_line(4)
        cards_grid.set_min_children_per_line(2)
        cards_grid.set_homogeneous(True)

        self._server_card = StatCard(_("Servers"), icon="network-server-symbolic")
        self._user_card = StatCard(_("Users"), icon="system-users-symbolic")
        self._host_card = StatCard(_("Hosts"), icon="computer-symbolic")
        self._group_card = StatCard(_("Groups"), icon="contact-new-symbolic")

        for card in (self._server_card, self._user_card,
                     self._host_card, self._group_card):
            cards_grid.insert(card, -1)

        content.append(cards_grid)

        # -- Certificate warnings --
        cert_label = Gtk.Label(label=_("Certificate Expiry Warnings"), xalign=0)
        cert_label.add_css_class("title-2")
        cert_label.set_margin_top(12)
        content.append(cert_label)

        self._cert_list = Gtk.ListBox()
        self._cert_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._cert_list.add_css_class("boxed-list")

        cert_placeholder = Adw.ActionRow()
        cert_placeholder.set_title(_("No certificate warnings"))
        cert_placeholder.set_subtitle(_("Connect to a server to check certificates"))
        self._cert_list.append(cert_placeholder)

        content.append(self._cert_list)

        # -- Replication topology --
        topo_label = Gtk.Label(label=_("Replication Topology"), xalign=0)
        topo_label.add_css_class("title-2")
        topo_label.set_margin_top(12)
        content.append(topo_label)

        self._topo_list = Gtk.ListBox()
        self._topo_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._topo_list.add_css_class("boxed-list")

        topo_placeholder = Adw.ActionRow()
        topo_placeholder.set_title(_("No replication data"))
        topo_placeholder.set_subtitle(_("Connect to a server to view topology"))
        self._topo_list.append(topo_placeholder)

        content.append(self._topo_list)

        # -- Service health --
        health_label = Gtk.Label(label=_("Service Health"), xalign=0)
        health_label.add_css_class("title-2")
        health_label.set_margin_top(12)
        content.append(health_label)

        self._health_list = Gtk.ListBox()
        self._health_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._health_list.add_css_class("boxed-list")

        for svc in ("KDC", "LDAP", "HTTP", "DNS", "CA"):
            row = Adw.ActionRow()
            row.set_title(svc)
            row.set_subtitle(_("Unknown"))
            row.add_prefix(Gtk.Image.new_from_icon_name("dialog-question-symbolic"))
            self._health_list.append(row)

        content.append(self._health_list)

        scrolled.set_child(content)
        self.append(scrolled)

    def refresh(self) -> None:
        """Fetch dashboard data from the server."""
        if not self.window or not self.window.client:
            return

        client = self.window.client

        def fetch() -> dict | str:
            try:
                return client.dashboard_data()
            except Exception as exc:
                return str(exc)

        def on_done(result: dict | str) -> None:
            if isinstance(result, str):
                log.error("Dashboard fetch failed: %s", result)
                return
            self._populate(result)

        def thread_target() -> None:
            result = fetch()
            GLib.idle_add(on_done, result)

        t = threading.Thread(target=thread_target, daemon=True)
        t.start()

    def _populate(self, data: dict) -> None:
        """Populate dashboard cards from batch result."""
        results = data if isinstance(data, list) else data.get("results", [])

        counts = []
        for entry in results:
            if isinstance(entry, dict):
                r = entry.get("result", entry)
                counts.append(r.get("count", 0))
            else:
                counts.append(0)

        while len(counts) < 5:
            counts.append(0)

        self._user_card.set_value(str(counts[0]))
        self._host_card.set_value(str(counts[1]))
        self._group_card.set_value(str(counts[2]))
        self._server_card.set_value(str(counts[3]))

        # Process certificates for warnings
        if len(results) > 4 and isinstance(results[4], dict):
            cert_result = results[4].get("result", results[4])
            certs = cert_result.get("result", [])
            self._update_cert_warnings(certs)

    def _update_cert_warnings(self, certs: list) -> None:
        """Update certificate warning list."""
        # Clear existing rows
        while True:
            row = self._cert_list.get_row_at_index(0)
            if row is None:
                break
            self._cert_list.remove(row)

        now = datetime.now(tz=timezone.utc)
        warnings = []

        for cert in certs:
            not_after = cert.get("valid_not_after")
            if not not_after:
                continue
            if isinstance(not_after, str):
                try:
                    exp = datetime.fromisoformat(not_after.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                continue
            remaining = (exp - now).days
            if remaining <= 90:
                subject = cert.get("subject", _("Unknown"))
                if isinstance(subject, dict):
                    subject = subject.get("CN", str(subject))
                warnings.append((subject, remaining))

        if not warnings:
            row = Adw.ActionRow()
            row.set_title(_("All certificates OK"))
            row.set_subtitle(_("No certificates expiring within 90 days"))
            row.add_prefix(
                Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            )
            self._cert_list.append(row)
        else:
            warnings.sort(key=lambda x: x[1])
            for subject, days in warnings:
                row_widget = CertWarningRow(str(subject), days)
                self._cert_list.append(row_widget)
