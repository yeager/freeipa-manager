"""CLI entry point for ipa-mgr."""

import argparse
import gettext
import sys

from . import __version__

_ = gettext.gettext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipa-mgr",
        description=_("FreeIPA Manager — CLI for FreeIPA administration"),
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--server", "-s",
        help=_("FreeIPA server hostname"),
    )
    parser.add_argument(
        "--realm", "-r",
        help=_("Kerberos realm"),
    )
    parser.add_argument(
        "--user", "-u",
        help=_("Username for password authentication"),
    )
    parser.add_argument(
        "--password", "-p",
        help=_("Password (omit to prompt)"),
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        default=False,
        help=_("Output in JSON format"),
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help=_("Suppress non-essential output"),
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        default=False,
        help=_("Disable SSL certificate verification"),
    )

    sub = parser.add_subparsers(dest="command", help=_("Available commands"))

    # connect
    sub.add_parser("connect", help=_("Test connection to a FreeIPA server"))

    # users
    users_parser = sub.add_parser("users", help=_("User management"))
    users_parser.add_argument(
        "action", nargs="?", default="list",
        choices=["list", "show"],
        help=_("Action to perform"),
    )
    users_parser.add_argument("login", nargs="?", help=_("User login for 'show'"))

    # groups
    sub.add_parser("groups", help=_("Group management"))

    # hosts
    sub.add_parser("hosts", help=_("Host management"))

    # certs
    certs_parser = sub.add_parser("certs", help=_("Certificate management"))
    certs_parser.add_argument(
        "action", nargs="?", default="list",
        choices=["list", "expiring"],
        help=_("Action to perform"),
    )
    certs_parser.add_argument(
        "--days", "-d", type=int, default=30,
        help=_("Days threshold for expiring certs (default: 30)"),
    )

    # policies
    policies_parser = sub.add_parser("policies", help=_("HBAC and sudo rules"))
    policies_parser.add_argument(
        "--type", "-t", default="hbac",
        choices=["hbac", "sudo"],
        help=_("Policy type (default: hbac)"),
    )

    # dns
    dns_parser = sub.add_parser("dns", help=_("DNS management"))
    dns_parser.add_argument(
        "action", nargs="?", default="zones",
        choices=["zones", "records"],
        help=_("Action to perform"),
    )
    dns_parser.add_argument("--zone", "-z", help=_("DNS zone for record listing"))

    # status
    sub.add_parser("status", help=_("Dashboard status summary"))

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    from .cli.commands import (
        cmd_certs,
        cmd_connect,
        cmd_dns,
        cmd_groups,
        cmd_hosts,
        cmd_policies,
        cmd_status,
        cmd_users,
    )

    dispatch = {
        "connect": cmd_connect,
        "users": cmd_users,
        "groups": cmd_groups,
        "hosts": cmd_hosts,
        "certs": cmd_certs,
        "policies": cmd_policies,
        "dns": cmd_dns,
        "status": cmd_status,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
