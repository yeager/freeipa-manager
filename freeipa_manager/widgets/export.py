"""CSV/JSON export dialog."""

import csv
import gettext
import io
import json

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

_ = gettext.gettext


def _flatten_row(row: dict, columns: list[str]) -> dict:
    """Flatten list values in a row for CSV export."""
    flat = {}
    for col in columns:
        val = row.get(col, "")
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        flat[col] = str(val) if val else ""
    return flat


def _to_csv(data: list[dict], columns: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow(_flatten_row(row, columns))
    return output.getvalue()


def _to_json(data: list[dict], columns: list[str]) -> str:
    filtered = []
    for row in data:
        filtered.append({col: row.get(col, "") for col in columns})
    return json.dumps(filtered, indent=2, default=str)


def export_dialog(parent: Gtk.Window, data: list[dict],
                  columns: list[str]) -> None:
    """Show an export format selection dialog, then save the file."""
    if not data:
        dialog = Adw.AlertDialog.new(
            _("Export"),
            _("No data to export."),
        )
        dialog.add_response("ok", _("OK"))
        dialog.present(parent)
        return

    dialog = Adw.AlertDialog.new(
        _("Export Data"),
        _("Choose the export format."),
    )
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("csv", _("CSV"))
    dialog.add_response("json", _("JSON"))
    dialog.set_response_appearance("csv", Adw.ResponseAppearance.SUGGESTED)

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "csv":
            content = _to_csv(data, columns)
            _save_file(parent, content, "export.csv")
        elif response == "json":
            content = _to_json(data, columns)
            _save_file(parent, content, "export.json")

    dialog.connect("response", on_response)
    dialog.present(parent)


def _save_file(parent: Gtk.Window, content: str, default_name: str) -> None:
    """Save content to a file using the native file chooser."""
    file_dialog = Gtk.FileDialog.new()
    file_dialog.set_initial_name(default_name)

    def on_save(_dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = file_dialog.save_finish(result)
            if gfile:
                path = gfile.get_path()
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
        except GLib.Error:
            pass  # User cancelled

    file_dialog.save(parent, None, on_save)
