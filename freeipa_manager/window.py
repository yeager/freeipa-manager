"""Main application window with sidebar navigation."""

import gettext
import logging
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .api import IPAClient  # noqa: E402
from .app import load_config, save_config  # noqa: E402

_ = gettext.gettext
log = logging.getLogger(__name__)

# Sidebar navigation items: (id, icon, label)
NAV_ITEMS = [
    ("dashboard", "computer-symbolic", _("Dashboard")),
    ("users", "system-users-symbolic", _("Users")),
    ("groups", "contact-new-symbolic", _("Groups")),
    ("hosts", "network-server-symbolic", _("Hosts")),
    ("policies", "security-high-symbolic", _("Policies")),
    ("dns", "network-workgroup-symbolic", _("DNS")),
    ("certs", "channel-secure-symbolic", _("Certificates")),
]


class FreeIPAWindow(Adw.ApplicationWindow):
    """Main window with split-view navigation."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            default_width=1100,
            default_height=700,
            title=_("FreeIPA Manager"),
            **kwargs,
        )

        self.client: IPAClient | None = None
        self._views: dict = {}
        self._current_view: str = "dashboard"

        self._setup_actions()
        self._build_ui()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _setup_actions(self) -> None:
        for nav_id, _, _ in NAV_ITEMS:
            action = Gio.SimpleAction.new(f"navigate-{nav_id}", None)
            action.connect("activate", self._on_navigate, nav_id)
            self.add_action(action)

        refresh = Gio.SimpleAction.new("refresh", None)
        refresh.connect("activate", self._on_refresh)
        self.add_action(refresh)

        search = Gio.SimpleAction.new("search", None)
        search.connect("activate", self._on_search_activate)
        self.add_action(search)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Outer toolbarview wrapping the split
        self._split = Adw.NavigationSplitView()
        self._split.set_min_sidebar_width(200)
        self._split.set_max_sidebar_width(260)

        # -- Sidebar --
        sidebar_page = Adw.NavigationPage.new(self._build_sidebar(), _("Navigation"))
        self._split.set_sidebar(sidebar_page)

        # -- Content --
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Status bar at the bottom
        self._status_label = Gtk.Label(label=_("Not connected"))
        self._status_label.add_css_class("dim-label")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_margin_start(8)
        self._status_label.set_margin_end(8)
        self._status_label.set_margin_top(4)
        self._status_label.set_margin_bottom(4)

        status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_bar.append(self._status_label)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(self._content_stack)
        content_box.set_vexpand(True)

        content_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_vbox.append(content_box)
        content_vbox.append(Gtk.Separator())
        content_vbox.append(status_bar)

        # Content header bar
        content_header = Adw.HeaderBar()
        self._content_title = Adw.WindowTitle.new(_("Dashboard"), "")
        content_header.set_title_widget(self._content_title)

        # Theme toggle button
        theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic")
        theme_btn.set_tooltip_text(_("Toggle Dark Theme"))
        theme_btn.set_action_name("app.theme")
        content_header.pack_end(theme_btn)

        # Refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh"))
        refresh_btn.set_action_name("win.refresh")
        content_header.pack_end(refresh_btn)

        content_toolbar = Adw.ToolbarView()
        content_toolbar.add_top_bar(content_header)
        content_toolbar.set_content(content_vbox)

        content_page = Adw.NavigationPage.new(content_toolbar, _("Content"))
        self._split.set_content(content_page)

        # Add placeholder pages
        self._add_placeholder_views()

        self.set_content(self._split)

    def _build_sidebar(self) -> Gtk.Widget:
        header = Adw.HeaderBar()
        header.set_show_title(True)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(self._build_app_menu())
        header.pack_end(menu_btn)

        sidebar_list = Gtk.ListBox()
        sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        sidebar_list.add_css_class("navigation-sidebar")
        sidebar_list.connect("row-selected", self._on_sidebar_row_selected)

        for nav_id, icon_name, label in NAV_ITEMS:
            row = Adw.ActionRow()
            row.set_title(label)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))
            row.nav_id = nav_id  # type: ignore[attr-defined]
            sidebar_list.append(row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(sidebar_list)
        scrolled.set_vexpand(True)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(scrolled)

        self._sidebar_list = sidebar_list
        return toolbar

    def _build_app_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu.append(_("About FreeIPA Manager"), "app.about")
        return menu

    def _add_placeholder_views(self) -> None:
        """Add initial placeholder views. Real views replace these once connected."""
        from .views.dashboard import DashboardView
        from .views.users import UsersView
        from .views.groups import GroupsView
        from .views.hosts import HostsView
        from .views.policies import PoliciesView
        from .views.dns import DNSView
        from .views.certs import CertsView

        view_classes = {
            "dashboard": DashboardView,
            "users": UsersView,
            "groups": GroupsView,
            "hosts": HostsView,
            "policies": PoliciesView,
            "dns": DNSView,
            "certs": CertsView,
        }

        for nav_id, cls in view_classes.items():
            view = cls(window=self)
            self._views[nav_id] = view
            self._content_stack.add_named(view, nav_id)

        self._content_stack.set_visible_child_name("dashboard")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_sidebar_row_selected(self, listbox: Gtk.ListBox,
                                  row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        nav_id = row.nav_id  # type: ignore[attr-defined]
        self._navigate_to(nav_id)

    def _on_navigate(self, _action: Gio.SimpleAction, _param: None,
                     nav_id: str) -> None:
        self._navigate_to(nav_id)

        # Also select the correct sidebar row
        for i, (nid, _, _) in enumerate(NAV_ITEMS):
            if nid == nav_id:
                row = self._sidebar_list.get_row_at_index(i)
                if row:
                    self._sidebar_list.select_row(row)
                break

    def _navigate_to(self, nav_id: str) -> None:
        self._current_view = nav_id
        self._content_stack.set_visible_child_name(nav_id)

        # Update title
        for nid, _, label in NAV_ITEMS:
            if nid == nav_id:
                self._content_title.set_title(label)
                break

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def show_connection_dialog(self) -> None:
        from .widgets.connection import ConnectionDialog
        dialog = ConnectionDialog(window=self)
        dialog.present(self)

    def connect_to_server(self, server: str, auth_method: str,
                          username: str = "", password: str = "",
                          verify_ssl: bool = True) -> None:
        """Establish connection to a FreeIPA server."""
        self.client = IPAClient(server, verify_ssl=verify_ssl)

        def do_connect() -> str | None:
            try:
                if auth_method == "password":
                    self.client.login_password(username, password)
                else:
                    self.client.login_kerberos()
                return None
            except Exception as exc:
                return str(exc)

        def on_done(error: str | None) -> None:
            if error:
                self._status_label.set_text(_("Connection failed: %s") % error)
                dialog = Adw.AlertDialog.new(
                    _("Connection Failed"),
                    str(error),
                )
                dialog.add_response("ok", _("OK"))
                dialog.present(self)
                self.client = None
            else:
                # Save config
                config = load_config()
                config["server"] = server
                config["auth_method"] = auth_method
                if auth_method == "password":
                    config["username"] = username
                save_config(config)

                now = datetime.now().strftime("%H:%M:%S")
                self._status_label.set_text(
                    _("Connected to %s — Last refresh: %s") % (server, now)
                )

                # Refresh views
                self._refresh_current_view()

        import threading

        def thread_target() -> None:
            error = do_connect()
            GLib.idle_add(on_done, error)

        t = threading.Thread(target=thread_target, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _on_refresh(self, _action: Gio.SimpleAction, _param: None) -> None:
        self._refresh_current_view()

    def _on_search_activate(self, _action: Gio.SimpleAction,
                            _param: None) -> None:
        view = self._views.get(self._current_view)
        if view and hasattr(view, "focus_search"):
            view.focus_search()

    def _refresh_current_view(self) -> None:
        view = self._views.get(self._current_view)
        if view and hasattr(view, "refresh"):
            view.refresh()

        now = datetime.now().strftime("%H:%M:%S")
        server = load_config().get("server", "?")
        self._status_label.set_text(
            _("Connected to %s — Last refresh: %s") % (server, now)
        )
