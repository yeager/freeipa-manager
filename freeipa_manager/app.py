"""GTK4/Adwaita application entry point."""

import gettext
import json
import logging
import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import __app_id__, __version__  # noqa: E402

_ = gettext.gettext
log = logging.getLogger(__name__)

CONFIG_DIR = Path(GLib.get_user_config_dir()) / "freeipa-manager"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load saved configuration."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


class FreeIPAApp(Adw.Application):
    """Main application class."""

    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.config = load_config()
        self._setup_actions()

    def _setup_actions(self) -> None:
        """Register application-level actions and keyboard shortcuts."""
        actions = [
            ("quit", self._on_quit, ["<primary>q"]),
            ("about", self._on_about, None),
            ("shortcuts", self._on_shortcuts, ["<primary>question"]),
            ("preferences", self._on_preferences, ["<primary>comma"]),
            ("theme", self._on_toggle_theme, ["<primary>t"]),
        ]
        for name, callback, accels in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

        # Navigation shortcuts
        self.set_accels_for_action("win.navigate-dashboard", ["<primary>1"])
        self.set_accels_for_action("win.navigate-users", ["<primary>2"])
        self.set_accels_for_action("win.navigate-groups", ["<primary>3"])
        self.set_accels_for_action("win.navigate-hosts", ["<primary>4"])
        self.set_accels_for_action("win.navigate-policies", ["<primary>5"])
        self.set_accels_for_action("win.navigate-dns", ["<primary>6"])
        self.set_accels_for_action("win.navigate-certs", ["<primary>7"])
        self.set_accels_for_action("win.refresh", ["<primary>r", "F5"])
        self.set_accels_for_action("win.search", ["<primary>f"])

    def do_activate(self) -> None:
        from .window import FreeIPAWindow

        win = self.props.active_window
        if not win:
            win = FreeIPAWindow(application=self)

        # Show welcome dialog on first run
        if not self.config.get("first_run_done"):
            self._show_welcome(win)
            self.config["first_run_done"] = True
            save_config(self.config)

        # Show connection dialog if no server configured
        if not self.config.get("server"):
            GLib.idle_add(win.show_connection_dialog)

        win.present()

    def _show_welcome(self, parent: Gtk.Window) -> None:
        """Show welcome dialog on first run."""
        dialog = Adw.AlertDialog.new(
            _("Welcome to FreeIPA Manager"),
            _(
                "Manage your FreeIPA server with an intuitive desktop interface.\n\n"
                "To get started, configure your FreeIPA server connection."
            ),
        )
        dialog.add_response("ok", _("Get Started"))
        dialog.set_default_response("ok")
        dialog.present(parent)

    def _on_quit(self, _action: Gio.SimpleAction, _param: None) -> None:
        self.quit()

    def _on_about(self, _action: Gio.SimpleAction, _param: None) -> None:
        win = self.props.active_window
        about = Adw.AboutDialog.new()
        about.set_application_name(_("FreeIPA Manager"))
        about.set_application_icon(__app_id__)
        about.set_version(__version__)
        about.set_developer_name("Daniel Nylander")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website("https://github.com/yeager/freeipa-manager")
        about.set_issue_url("https://github.com/yeager/freeipa-manager/issues")
        about.set_developers(["Daniel Nylander <daniel@danielnylander.se>"])
        about.set_copyright("© 2024 Daniel Nylander")
        about.set_comments(
            _("GTK4/Adwaita GUI and CLI for managing FreeIPA servers")
        )

        # Debug info
        debug_lines = [
            f"freeipa-manager {__version__}",
            f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
            f"libadwaita {Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}",
            f"Python {sys.version}",
            f"OS: {os.uname().sysname} {os.uname().release}",
        ]
        about.set_debug_info("\n".join(debug_lines))
        about.set_debug_info_filename("freeipa-manager-debug.txt")

        about.present(win)

    def _on_shortcuts(self, _action: Gio.SimpleAction, _param: None) -> None:
        win = self.props.active_window
        builder = Gtk.Builder.new_from_string(SHORTCUTS_UI, -1)
        shortcuts_win = builder.get_object("shortcuts")
        shortcuts_win.set_transient_for(win)
        shortcuts_win.present()

    def _on_preferences(self, _action: Gio.SimpleAction, _param: None) -> None:
        pass  # placeholder for preferences dialog

    def _on_toggle_theme(self, _action: Gio.SimpleAction, _param: None) -> None:
        sm = Adw.StyleManager.get_default()
        if sm.get_dark():
            sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)


SHORTCUTS_UI = """\
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkShortcutsWindow" id="shortcuts">
    <property name="modal">1</property>
    <child>
      <object class="GtkShortcutsSection">
        <property name="section-name">shortcuts</property>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="title" translatable="yes">General</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Keyboard Shortcuts</property>
                <property name="accelerator">&lt;primary&gt;question</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Toggle Dark Theme</property>
                <property name="accelerator">&lt;primary&gt;t</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Refresh</property>
                <property name="accelerator">&lt;primary&gt;r</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Search</property>
                <property name="accelerator">&lt;primary&gt;f</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Quit</property>
                <property name="accelerator">&lt;primary&gt;q</property>
              </object>
            </child>
          </object>
        </child>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="title" translatable="yes">Navigation</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Dashboard</property>
                <property name="accelerator">&lt;primary&gt;1</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Users</property>
                <property name="accelerator">&lt;primary&gt;2</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Groups</property>
                <property name="accelerator">&lt;primary&gt;3</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Hosts</property>
                <property name="accelerator">&lt;primary&gt;4</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Policies</property>
                <property name="accelerator">&lt;primary&gt;5</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">DNS</property>
                <property name="accelerator">&lt;primary&gt;6</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title" translatable="yes">Certificates</property>
                <property name="accelerator">&lt;primary&gt;7</property>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>
"""


def main() -> None:
    """GUI entry point."""
    app = FreeIPAApp()
    app.run(sys.argv)
