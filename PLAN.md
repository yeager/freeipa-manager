# freeipa-manager — FreeIPA GTK4 Client + CLI + Dashboard

## Architecture
- **Module**: `freeipa_manager`
- **Package**: `freeipa-manager`
- **GitHub**: yeager/freeipa-manager
- **License**: GPL-3.0

## Components

### 1. GTK4/Adwaita GUI
- **Dashboard tab**: server status, cert expiry warnings, replication topology, service health
- **Users tab**: list/search/create/edit/disable users, password reset, group membership
- **Groups tab**: list/search/create/edit groups, member management
- **Hosts tab**: registered hosts, enrollment status, host groups
- **Policies tab**: HBAC rules, sudo rules, password policies
- **DNS tab**: zones, records, forward/reverse
- **Certificates tab**: cert list, expiry tracking, renewal

### 2. CLI (`ipa-mgr`)
- `ipa-mgr connect <server>` — test connection
- `ipa-mgr users list [--json] [-q]`
- `ipa-mgr users show <login>`
- `ipa-mgr groups list`
- `ipa-mgr hosts list`
- `ipa-mgr certs expiring [--days 30]`
- `ipa-mgr status` — dashboard summary as text
- Exit codes + JSON output for scripting

### 3. Dashboard View
- Certificate expiry timeline (warning/critical)
- Replication agreements + status
- Service status (KDC, LDAP, HTTP, DNS, CA)
- Recent changes / audit log
- Quick stats (users, hosts, groups count)

## Tech Stack
- Python 3.10+
- GTK4 + libadwaita
- python-gssapi (Kerberos auth)
- requests + requests-gssapi
- FreeIPA JSON-RPC: `https://<server>/ipa/json`
- gettext for i18n
- argparse for CLI

## FreeIPA JSON-RPC API
- Endpoint: `https://<server>/ipa/json`
- Auth: Kerberos (Negotiate) or session cookie
- Request: `{"method": "user_find", "params": [[""], {"sizelimit": 0}]}`
- Response: `{"result": {"result": [...], "count": N}}`

## Cross-Suite Features
- Theme toggle (light/dark/system)
- Keyboard shortcuts
- Status bar with timestamps
- CSV/JSON export
- "Copy Debug Info"
- Welcome dialog
- Desktop notifications (cert expiry)
- man page + po4a

## File Structure
```
freeipa_manager/
├── __init__.py          # version
├── __main__.py          # CLI entry
├── app.py               # GtkApplication
├── api.py               # FreeIPA JSON-RPC client
├── auth.py              # Kerberos/session auth
├── window.py            # Main AdwApplicationWindow
├── views/
│   ├── dashboard.py     # Dashboard/overview
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
    ├── __init__.py
    └── commands.py      # CLI commands
po/
├── POTFILES.in
├── freeipa-manager.pot
└── sv.po
data/
├── se.danielnylander.freeipa-manager.desktop
├── se.danielnylander.freeipa-manager.svg
└── se.danielnylander.freeipa-manager.metainfo.xml
man/
└── ipa-mgr.1
```
