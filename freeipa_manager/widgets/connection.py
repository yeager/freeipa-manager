"""Connection dialog for FreeIPA server configuration."""

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from ..app import load_config  # noqa: E402

_ = gettext.gettext


class ConnectionDialog:
    """Dialog for configuring FreeIPA server connection."""

    def __init__(self, window: "FreeIPAWindow") -> None:  # noqa: F821
        self.window = window

        config = load_config()

        self._dialog = Adw.AlertDialog.new(
            _("Connect to FreeIPA Server"),
            _("Enter your FreeIPA server details to connect."),
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(4)
        box.set_margin_end(4)

        # Server entry
        self._server_entry = Adw.EntryRow()
        self._server_entry.set_title(_("Server Hostname"))
        self._server_entry.set_text(config.get("server", ""))
        box.append(self._server_entry)

        # Auth method
        self._auth_combo = Adw.ComboRow()
        self._auth_combo.set_title(_("Authentication Method"))
        self._auth_combo.set_model(Gtk.StringList.new([
            _("Kerberos (GSSAPI)"),
            _("Password"),
        ]))
        saved_method = config.get("auth_method", "kerberos")
        self._auth_combo.set_selected(1 if saved_method == "password" else 0)
        self._auth_combo.connect("notify::selected", self._on_auth_changed)
        box.append(self._auth_combo)

        # Username (for password auth)
        self._user_entry = Adw.EntryRow()
        self._user_entry.set_title(_("Username"))
        self._user_entry.set_text(config.get("username", ""))
        box.append(self._user_entry)

        # Password
        self._pass_entry = Adw.PasswordEntryRow()
        self._pass_entry.set_title(_("Password"))
        box.append(self._pass_entry)

        # SSL verify toggle
        self._ssl_switch = Adw.SwitchRow()
        self._ssl_switch.set_title(_("Verify SSL Certificate"))
        self._ssl_switch.set_active(config.get("verify_ssl", True))
        box.append(self._ssl_switch)

        # Update visibility based on auth method
        self._update_auth_fields()

        self._dialog.set_extra_child(box)
        self._dialog.add_response("cancel", _("Cancel"))
        self._dialog.add_response("connect", _("Connect"))
        self._dialog.set_response_appearance(
            "connect", Adw.ResponseAppearance.SUGGESTED
        )
        self._dialog.set_default_response("connect")
        self._dialog.connect("response", self._on_response)

    def present(self, parent: Gtk.Window) -> None:
        self._dialog.present(parent)

    def _on_auth_changed(self, combo: Adw.ComboRow, _pspec: object) -> None:
        self._update_auth_fields()

    def _update_auth_fields(self) -> None:
        is_password = self._auth_combo.get_selected() == 1
        self._user_entry.set_visible(is_password)
        self._pass_entry.set_visible(is_password)

    def _on_response(self, dialog: Adw.AlertDialog, response: str) -> None:
        if response != "connect":
            return

        server = self._server_entry.get_text().strip()
        if not server:
            err = Adw.AlertDialog.new(
                _("Error"), _("Server hostname is required.")
            )
            err.add_response("ok", _("OK"))
            err.present(self.window)
            return

        auth_method = "password" if self._auth_combo.get_selected() == 1 else "kerberos"
        username = self._user_entry.get_text().strip()
        password = self._pass_entry.get_text()
        verify_ssl = self._ssl_switch.get_active()

        self.window.connect_to_server(
            server=server,
            auth_method=auth_method,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
        )
