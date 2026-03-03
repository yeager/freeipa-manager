Build a FreeIPA management tool: GTK4/Adwaita GUI + CLI. Follow PLAN.md exactly.

## Critical Rules
- Python 3.10+, GTK4 + libadwaita
- Module name: freeipa_manager
- Package name: freeipa-manager
- CLI command: ipa-mgr
- App ID: se.danielnylander.freeipa-manager
- Author: Daniel Nylander <daniel@danielnylander.se>
- License: GPL-3.0
- All UI strings via gettext _()
- English display names, Swedish via .po
- Follow the EXACT file structure from PLAN.md

## API Client (api.py)
- FreeIPA JSON-RPC at https://<server>/ipa/json
- Headers: Referer, Content-Type application/json, Accept
- Auth via python-gssapi (Negotiate) OR username/password session cookie
- All methods return Python dicts
- Methods needed: user_find, user_show, user_add, user_mod, user_disable, user_enable,
  group_find, group_show, group_add_member, host_find, host_show,
  hbacrule_find, sudorule_find, dnszone_find, dnsrecord_find,
  cert_find, ca_is_enabled, server_find, topologysegment_find,
  batch (for dashboard multi-call)

## GUI (window.py)
- AdwApplicationWindow with AdwNavigationSplitView (sidebar + content)
- Sidebar: Dashboard, Users, Groups, Hosts, Policies, DNS, Certificates
- Connection dialog on first launch (server URL, auth method)
- Store last connection in GSettings or simple JSON config

## Dashboard View
- Card grid: server count, user count, host count, group count
- Certificate expiry warnings (< 30 days = red, < 90 days = yellow)
- Replication topology status
- Service health indicators

## All Views
- Search/filter bar at top
- List with columns (GtkColumnView)
- Click row → detail panel
- Create/Edit dialogs
- CSV/JSON export button
- Keyboard shortcuts

## CLI (__main__.py)
- argparse subcommands: connect, users, groups, hosts, certs, policies, dns, status
- --json flag for JSON output
- -q quiet flag
- Proper exit codes (0 ok, 1 error, 2 auth fail)
- --server and --realm flags (or from config)

## Cross-suite features
- Theme toggle (Adw.StyleManager)
- Keyboard shortcuts dialog
- Status bar with last-refresh timestamp
- Copy Debug Info (about dialog)
- Welcome dialog on first run
- Desktop notifications for cert expiry
- About dialog: Adw.AboutDialog with present(parent)

## Data files
- .desktop file with proper Categories=System;Network;
- SVG icon (shield + key motif, purple/blue gradient)
- metainfo.xml (AppStream)

## pyproject.toml
- Build with setuptools
- Entry points: gui = freeipa_manager.app:main, cli = freeipa_manager.__main__:main
- Dependencies: PyGObject, requests, gssapi

## Don't forget
- po/POTFILES.in listing all .py files
- Generate .pot with xgettext
- Create sv.po with Swedish translations for all UI strings
- man page for ipa-mgr (man/ipa-mgr.1)
- README.md in English
- NEVER use translate_url in AboutDialog (not supported in GTK4)
- AboutDialog uses present(parent)
- *_ not *_args for gettext shadowing

Build everything. Make it complete and working.
