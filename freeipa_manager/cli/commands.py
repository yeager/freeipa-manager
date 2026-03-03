"""CLI command implementations for ipa-mgr."""

import csv
import gettext
import io
import json
import sys
from datetime import datetime, timezone
from typing import Any

from ..api import IPAClient, IPAError
from ..auth import AuthError

_ = gettext.gettext


def _get_client(args: Any) -> IPAClient:
    """Create and authenticate an IPAClient from CLI args."""
    server = args.server
    if not server:
        print(_("Error: --server is required"), file=sys.stderr)
        sys.exit(1)

    client = IPAClient(server, verify_ssl=not getattr(args, "no_verify", False))

    try:
        if args.user:
            password = args.password
            if not password:
                import getpass
                password = getpass.getpass(_("Password: "))
            client.login_password(args.user, password)
        else:
            client.login_kerberos()
    except AuthError as exc:
        if not args.quiet:
            print(_("Authentication failed: %s") % exc, file=sys.stderr)
        sys.exit(2)

    return client


def _output(data: Any, args: Any, columns: list[str] | None = None) -> None:
    """Print data as JSON or formatted table."""
    if args.json:
        json.dump(data, sys.stdout, indent=2, default=str)
        print()
        return

    if isinstance(data, list) and columns:
        _print_table(data, columns, quiet=args.quiet)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            print(f"  {key}: {value}")
    else:
        print(data)


def _print_table(rows: list[dict], columns: list[str],
                 quiet: bool = False) -> None:
    """Print rows as an aligned table."""
    if not rows:
        if not quiet:
            print(_("No results found."))
        return

    widths = {col: len(col) for col in columns}
    str_rows = []
    for row in rows:
        str_row = {}
        for col in columns:
            val = row.get(col, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            str_row[col] = str(val)
            widths[col] = max(widths[col], len(str_row[col]))
        str_rows.append(str_row)

    if not quiet:
        header = "  ".join(col.ljust(widths[col]) for col in columns)
        print(header)
        print("  ".join("-" * widths[col] for col in columns))

    for str_row in str_rows:
        line = "  ".join(str_row[col].ljust(widths[col]) for col in columns)
        print(line)

    if not quiet:
        print(_("\n%d result(s)") % len(str_rows))


# ------------------------------------------------------------------
# Subcommands
# ------------------------------------------------------------------

def cmd_connect(args: Any) -> None:
    """Test connection to a FreeIPA server."""
    client = _get_client(args)
    try:
        result = client.server_find()
        servers = result.get("result", [])
        if not args.quiet:
            print(_("Connected to %s") % args.server)
            print(_("Servers: %d") % len(servers))
            for srv in servers:
                name = srv.get("cn", [""])[0] if isinstance(srv.get("cn"), list) else srv.get("cn", "")
                print(f"  - {name}")
    except IPAError as exc:
        print(_("Connection failed: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_users(args: Any) -> None:
    """List or show users."""
    client = _get_client(args)
    try:
        if args.action == "show" and args.login:
            result = client.user_show(args.login, all=True)
            _output(result.get("result", {}), args)
        else:
            result = client.user_find(sizelimit=0)
            users = result.get("result", [])
            _output(users, args, columns=["uid", "givenname", "sn", "nsaccountlock"])
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_groups(args: Any) -> None:
    """List groups."""
    client = _get_client(args)
    try:
        result = client.group_find(sizelimit=0)
        groups = result.get("result", [])
        _output(groups, args, columns=["cn", "description", "gidnumber"])
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_hosts(args: Any) -> None:
    """List hosts."""
    client = _get_client(args)
    try:
        result = client.host_find(sizelimit=0)
        hosts = result.get("result", [])
        _output(hosts, args, columns=["fqdn", "description", "has_keytab"])
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_certs(args: Any) -> None:
    """List or check expiring certificates."""
    client = _get_client(args)
    try:
        result = client.cert_find(sizelimit=0)
        certs = result.get("result", [])

        if args.action == "expiring":
            days = getattr(args, "days", 30) or 30
            now = datetime.now(tz=timezone.utc)
            expiring = []
            for cert in certs:
                not_after = cert.get("valid_not_after")
                if not_after:
                    if isinstance(not_after, str):
                        try:
                            exp = datetime.fromisoformat(not_after.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                    else:
                        continue
                    remaining = (exp - now).days
                    if remaining <= days:
                        cert["_days_remaining"] = remaining
                        expiring.append(cert)
            _output(expiring, args, columns=["serial_number", "subject", "_days_remaining"])
        else:
            _output(certs, args, columns=["serial_number", "subject", "status", "valid_not_after"])
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_policies(args: Any) -> None:
    """List HBAC and sudo rules."""
    client = _get_client(args)
    try:
        if args.type == "sudo":
            result = client.sudorule_find(sizelimit=0)
            rules = result.get("result", [])
            _output(rules, args, columns=["cn", "ipaenabledflag", "description"])
        else:
            result = client.hbacrule_find(sizelimit=0)
            rules = result.get("result", [])
            _output(rules, args, columns=["cn", "ipaenabledflag", "description"])
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_dns(args: Any) -> None:
    """List DNS zones or records."""
    client = _get_client(args)
    try:
        if args.action == "records" and args.zone:
            result = client.dnsrecord_find(args.zone)
            records = result.get("result", [])
            _output(records, args, columns=["idnsname", "arecord", "cnamerecord"])
        else:
            result = client.dnszone_find()
            zones = result.get("result", [])
            _output(zones, args, columns=["idnsname", "idnszoneactive"])
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def cmd_status(args: Any) -> None:
    """Show dashboard status summary."""
    client = _get_client(args)
    try:
        data = client.dashboard_data()
        results = data if isinstance(data, list) else data.get("results", [])

        labels = [
            _("Users"), _("Hosts"), _("Groups"), _("Servers"), _("Certificates"),
        ]

        if not args.quiet:
            print(_("=== FreeIPA Dashboard ==="))
            print()

        for i, label in enumerate(labels):
            if i < len(results):
                entry = results[i]
                result = entry.get("result", entry) if isinstance(entry, dict) else {}
                count = result.get("count", "?")
                print(f"  {label}: {count}")

        if not args.quiet:
            print()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(_("Last updated: %s") % now)
    except IPAError as exc:
        print(_("Error: %s") % exc, file=sys.stderr)
        sys.exit(1)


def export_csv(data: list[dict], columns: list[str]) -> str:
    """Export data as CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        flat = {}
        for col in columns:
            val = row.get(col, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            flat[col] = val
        writer.writerow(flat)
    return output.getvalue()
