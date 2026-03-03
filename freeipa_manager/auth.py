"""Authentication helpers for FreeIPA JSON-RPC API."""

import gettext
import logging
from typing import Optional

import requests

_ = gettext.gettext
log = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when authentication fails."""


class KerberosAuth:
    """Authenticate using a Kerberos ticket (GSSAPI/Negotiate)."""

    def __init__(self, server: str, verify_ssl: bool = True) -> None:
        self.server = server
        self.verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None

    def login(self) -> requests.Session:
        try:
            from requests_gssapi import HTTPSPNEGOAuth
        except ImportError:
            try:
                from requests_kerberos import HTTPKerberosAuth as HTTPSPNEGOAuth
            except ImportError:
                import gssapi  # noqa: F401 — ensure gssapi is available

                raise AuthError(
                    _("Neither requests-gssapi nor requests-kerberos is installed")
                )

        session = requests.Session()
        session.verify = self.verify_ssl

        login_url = f"https://{self.server}/ipa/session/login_kerberos"
        headers = {"Referer": f"https://{self.server}/ipa"}

        resp = session.post(
            login_url, headers=headers, auth=HTTPSPNEGOAuth()
        )

        if resp.status_code != 200:
            raise AuthError(
                _("Kerberos authentication failed (HTTP %d)") % resp.status_code
            )

        log.info("Kerberos authentication successful for %s", self.server)
        self._session = session
        return session


class PasswordAuth:
    """Authenticate using username and password (session cookie)."""

    def __init__(self, server: str, verify_ssl: bool = True) -> None:
        self.server = server
        self.verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None

    def login(self, username: str, password: str) -> requests.Session:
        session = requests.Session()
        session.verify = self.verify_ssl

        login_url = f"https://{self.server}/ipa/session/login_password"
        headers = {
            "Referer": f"https://{self.server}/ipa",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
        }
        data = {"user": username, "password": password}

        resp = session.post(login_url, headers=headers, data=data)

        if resp.status_code == 401:
            raise AuthError(_("Invalid username or password"))
        if resp.status_code != 200:
            raise AuthError(
                _("Password authentication failed (HTTP %d)") % resp.status_code
            )

        log.info("Password authentication successful for %s@%s", username, self.server)
        self._session = session
        return session
