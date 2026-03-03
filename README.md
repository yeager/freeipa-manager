# FreeIPA Manager

A GTK4/Adwaita graphical interface and command-line tool for managing FreeIPA identity management servers.

## Features

- **Dashboard** — Server overview, certificate expiry warnings, replication topology, service health
- **User Management** — List, search, create, edit, disable/enable users
- **Group Management** — List, search, create groups and manage members
- **Host Management** — View registered hosts and enrollment status
- **Policy Management** — Browse HBAC and sudo rules
- **DNS Management** — Browse DNS zones and records
- **Certificate Tracking** — List certificates, track expiry, desktop notifications
- **CLI** — Full command-line interface for scripting and automation
- **Export** — CSV and JSON export for all data views
- **i18n** — English and Swedish translations via gettext

## Requirements

- Python 3.10+
- GTK4 and libadwaita
- A FreeIPA server with JSON-RPC API access

### Python Dependencies

- PyGObject >= 3.42
- requests >= 2.28
- gssapi >= 1.7

For Kerberos authentication, one of:
- requests-gssapi
- requests-kerberos

## Installation

```bash
pip install .
```

## Usage

### GUI

```bash
freeipa-manager
```

### CLI

```bash
# Test connection
ipa-mgr -s ipa.example.com connect

# List users
ipa-mgr -s ipa.example.com users list

# Show user details
ipa-mgr -s ipa.example.com users show admin

# List users as JSON
ipa-mgr -s ipa.example.com --json users list

# Expiring certificates
ipa-mgr -s ipa.example.com certs expiring --days 60

# Dashboard summary
ipa-mgr -s ipa.example.com status

# Password authentication
ipa-mgr -s ipa.example.com -u admin users list
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication failure |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+1–7 | Navigate to view |
| Ctrl+R / F5 | Refresh |
| Ctrl+F | Search |
| Ctrl+T | Toggle dark theme |
| Ctrl+? | Keyboard shortcuts |
| Ctrl+Q | Quit |

## Project Structure

```
freeipa_manager/
├── __init__.py          # Version
├── __main__.py          # CLI entry point
├── app.py               # GtkApplication
├── api.py               # FreeIPA JSON-RPC client
├── auth.py              # Kerberos/session auth
├── window.py            # Main AdwApplicationWindow
├── views/
│   ├── dashboard.py     # Dashboard overview
│   ├── users.py         # User management
│   ├── groups.py        # Group management
│   ├── hosts.py         # Host management
│   ├── policies.py      # HBAC/sudo rules
│   ├── dns.py           # DNS zones/records
│   └── certs.py         # Certificate management
├── widgets/
│   ├── connection.py    # Connection dialog
│   ├── search.py        # Search bar widget
│   └── export.py        # CSV/JSON export
└── cli/
    └── commands.py      # CLI command implementations
```

## License

GPL-3.0-only — see [LICENSE](LICENSE) for details.

## Author

Daniel Nylander <daniel@danielnylander.se>
