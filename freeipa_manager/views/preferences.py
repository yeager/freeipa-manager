"""Preferences view with simple and advanced settings."""

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from ..app import load_config, save_config  # noqa: E402

_ = gettext.gettext


class PreferencesView(Gtk.Box):
    """Settings view shown in the sidebar bottom area."""

    def __init__(self, window=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.window = window
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_margin_top(16)
        self.set_margin_bottom(16)

        self.config = load_config()

        # Title
        title = Gtk.Label(label=_("Settings"))
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        title.set_margin_bottom(16)
        self.append(title)

        # Simple settings
        simple_group = Adw.PreferencesGroup()
        simple_group.set_title(_("General"))
        simple_group.set_description(_("Common settings"))

        # Auto-connect on startup
        self._auto_connect = Adw.SwitchRow()
        self._auto_connect.set_title(_("Auto-connect on Startup"))
        self._auto_connect.set_subtitle(_("Automatically connect to the last server"))
        self._auto_connect.set_active(self.config.get("auto_connect", False))
        self._auto_connect.connect("notify::active", self._on_setting_changed)
        simple_group.add(self._auto_connect)

        # Show notifications
        self._notifications = Adw.SwitchRow()
        self._notifications.set_title(_("Desktop Notifications"))
        self._notifications.set_subtitle(_("Show notifications for important events"))
        self._notifications.set_active(self.config.get("notifications", True))
        self._notifications.connect("notify::active", self._on_setting_changed)
        simple_group.add(self._notifications)

        # Refresh interval
        self._refresh_row = Adw.ComboRow()
        self._refresh_row.set_title(_("Auto-refresh Interval"))
        self._refresh_row.set_subtitle(_("How often to refresh data from server"))
        intervals = Gtk.StringList.new([
            _("Disabled"),
            _("30 seconds"),
            _("1 minute"),
            _("5 minutes"),
            _("15 minutes"),
        ])
        self._refresh_row.set_model(intervals)
        interval_map = {0: 0, 30: 1, 60: 2, 300: 3, 900: 4}
        current = self.config.get("refresh_interval", 0)
        self._refresh_row.set_selected(interval_map.get(current, 0))
        self._refresh_row.connect("notify::selected", self._on_setting_changed)
        simple_group.add(self._refresh_row)

        # Items per page
        self._page_size = Adw.SpinRow.new_with_range(10, 200, 10)
        self._page_size.set_title(_("Items per Page"))
        self._page_size.set_subtitle(_("Number of entries shown in list views"))
        self._page_size.set_value(self.config.get("page_size", 50))
        self._page_size.connect("notify::value", self._on_setting_changed)
        simple_group.add(self._page_size)

        self.append(simple_group)

        # Separator
        sep = Gtk.Separator()
        sep.set_margin_top(16)
        sep.set_margin_bottom(8)
        self.append(sep)

        # Advanced settings (in expander)
        advanced_expander = Adw.ExpanderRow()
        advanced_expander.set_title(_("Advanced Settings"))
        advanced_expander.set_subtitle(_("Connection and security options"))
        advanced_expander.set_enable_expansion(True)
        advanced_expander.set_expanded(False)

        # SSL verification
        self._verify_ssl = Adw.SwitchRow()
        self._verify_ssl.set_title(_("Verify SSL Certificates"))
        self._verify_ssl.set_subtitle(_("Disable only for testing environments"))
        self._verify_ssl.set_active(self.config.get("verify_ssl", True))
        self._verify_ssl.connect("notify::active", self._on_setting_changed)
        advanced_expander.add_row(self._verify_ssl)

        # Connection timeout
        self._timeout = Adw.SpinRow.new_with_range(5, 120, 5)
        self._timeout.set_title(_("Connection Timeout (seconds)"))
        self._timeout.set_subtitle(_("Maximum time to wait for server response"))
        self._timeout.set_value(self.config.get("timeout", 30))
        self._timeout.connect("notify::value", self._on_setting_changed)
        advanced_expander.add_row(self._timeout)

        # Max concurrent requests
        self._max_requests = Adw.SpinRow.new_with_range(1, 20, 1)
        self._max_requests.set_title(_("Max Concurrent Requests"))
        self._max_requests.set_subtitle(_("Number of parallel API requests"))
        self._max_requests.set_value(self.config.get("max_requests", 5))
        self._max_requests.connect("notify::value", self._on_setting_changed)
        advanced_expander.add_row(self._max_requests)

        # Log level
        self._log_level = Adw.ComboRow()
        self._log_level.set_title(_("Log Level"))
        self._log_level.set_subtitle(_("Verbosity of application logging"))
        levels = Gtk.StringList.new(["ERROR", "WARNING", "INFO", "DEBUG"])
        self._log_level.set_model(levels)
        level_map = {"ERROR": 0, "WARNING": 1, "INFO": 2, "DEBUG": 3}
        self._log_level.set_selected(level_map.get(self.config.get("log_level", "WARNING"), 1))
        self._log_level.connect("notify::selected", self._on_setting_changed)
        advanced_expander.add_row(self._log_level)

        # Export format
        self._export_format = Adw.ComboRow()
        self._export_format.set_title(_("Default Export Format"))
        self._export_format.set_subtitle(_("Format for data exports"))
        formats = Gtk.StringList.new(["CSV", "JSON"])
        self._export_format.set_model(formats)
        fmt_map = {"csv": 0, "json": 1}
        self._export_format.set_selected(fmt_map.get(self.config.get("export_format", "csv"), 0))
        self._export_format.connect("notify::selected", self._on_setting_changed)
        advanced_expander.add_row(self._export_format)

        advanced_group = Adw.PreferencesGroup()
        advanced_group.add(advanced_expander)
        self.append(advanced_group)

        # Reset button
        reset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        reset_box.set_halign(Gtk.Align.END)
        reset_box.set_margin_top(24)

        reset_btn = Gtk.Button(label=_("Reset to Defaults"))
        reset_btn.add_css_class("destructive-action")
        reset_btn.connect("clicked", self._on_reset)
        reset_box.append(reset_btn)
        self.append(reset_box)

    def _on_setting_changed(self, *_args):
        """Save all settings when any value changes."""
        interval_values = [0, 30, 60, 300, 900]
        level_values = ["ERROR", "WARNING", "INFO", "DEBUG"]
        format_values = ["csv", "json"]

        self.config["auto_connect"] = self._auto_connect.get_active()
        self.config["notifications"] = self._notifications.get_active()
        self.config["refresh_interval"] = interval_values[self._refresh_row.get_selected()]
        self.config["page_size"] = int(self._page_size.get_value())
        self.config["verify_ssl"] = self._verify_ssl.get_active()
        self.config["timeout"] = int(self._timeout.get_value())
        self.config["max_requests"] = int(self._max_requests.get_value())
        self.config["log_level"] = level_values[self._log_level.get_selected()]
        self.config["export_format"] = format_values[self._export_format.get_selected()]

        save_config(self.config)

    def _on_reset(self, _btn):
        """Reset all settings to defaults."""
        self._auto_connect.set_active(False)
        self._notifications.set_active(True)
        self._refresh_row.set_selected(0)
        self._page_size.set_value(50)
        self._verify_ssl.set_active(True)
        self._timeout.set_value(30)
        self._max_requests.set_value(5)
        self._log_level.set_selected(1)
        self._export_format.set_selected(0)
