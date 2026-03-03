"""FreeIPA JSON-RPC API client."""

import gettext
import json
import logging
from typing import Any, Optional

import requests

from .auth import AuthError, KerberosAuth, PasswordAuth

_ = gettext.gettext
log = logging.getLogger(__name__)


class IPAError(Exception):
    """Raised when a FreeIPA API call fails."""


class IPAClient:
    """Client for the FreeIPA JSON-RPC API.

    All public methods return plain Python dicts.
    """

    API_VERSION = "2.254"

    def __init__(
        self,
        server: str,
        verify_ssl: bool = True,
    ) -> None:
        self.server = server
        self.verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return f"https://{self.server}/ipa"

    @property
    def json_url(self) -> str:
        return f"{self.base_url}/json"

    @property
    def connected(self) -> bool:
        return self._session is not None

    def login_kerberos(self) -> None:
        """Authenticate with a Kerberos ticket."""
        auth = KerberosAuth(self.server, verify_ssl=self.verify_ssl)
        self._session = auth.login()

    def login_password(self, username: str, password: str) -> None:
        """Authenticate with username and password."""
        auth = PasswordAuth(self.server, verify_ssl=self.verify_ssl)
        self._session = auth.login(username, password)

    def logout(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Low-level RPC
    # ------------------------------------------------------------------

    def _rpc(self, method: str, args: list | None = None,
             params: dict | None = None) -> dict:
        if not self._session:
            raise IPAError(_("Not connected — call login first"))

        args = args or [""]
        params = params or {}
        params.setdefault("version", self.API_VERSION)

        payload = {
            "method": method,
            "params": [args, params],
        }

        headers = {
            "Referer": self.base_url,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        resp = self._session.post(
            self.json_url,
            data=json.dumps(payload),
            headers=headers,
        )

        if resp.status_code == 401:
            raise AuthError(_("Session expired — please reconnect"))
        if resp.status_code != 200:
            raise IPAError(_("HTTP %d from %s") % (resp.status_code, method))

        body = resp.json()
        if body.get("error"):
            err = body["error"]
            raise IPAError(
                f"{err.get('name', 'UnknownError')}: {err.get('message', '')}"
            )

        return body.get("result", {})

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def user_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("user_find", [criteria], kw)

    def user_show(self, uid: str, **kw: Any) -> dict:
        return self._rpc("user_show", [uid], kw)

    def user_add(self, uid: str, **kw: Any) -> dict:
        return self._rpc("user_add", [uid], kw)

    def user_mod(self, uid: str, **kw: Any) -> dict:
        return self._rpc("user_mod", [uid], kw)

    def user_disable(self, uid: str) -> dict:
        return self._rpc("user_disable", [uid])

    def user_enable(self, uid: str) -> dict:
        return self._rpc("user_enable", [uid])

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def group_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("group_find", [criteria], kw)

    def group_show(self, cn: str, **kw: Any) -> dict:
        return self._rpc("group_show", [cn], kw)

    def group_add_member(self, cn: str, **kw: Any) -> dict:
        return self._rpc("group_add_member", [cn], kw)

    # ------------------------------------------------------------------
    # Hosts
    # ------------------------------------------------------------------

    def host_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("host_find", [criteria], kw)

    def host_show(self, fqdn: str, **kw: Any) -> dict:
        return self._rpc("host_show", [fqdn], kw)

    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------

    def hbacrule_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("hbacrule_find", [criteria], kw)

    def sudorule_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("sudorule_find", [criteria], kw)

    # ------------------------------------------------------------------
    # DNS
    # ------------------------------------------------------------------

    def dnszone_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("dnszone_find", [criteria], kw)

    def dnsrecord_find(self, zone: str, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("dnsrecord_find", [zone, criteria], kw)

    # ------------------------------------------------------------------
    # Certificates
    # ------------------------------------------------------------------

    def cert_find(self, **kw: Any) -> dict:
        return self._rpc("cert_find", [""], kw)

    def ca_is_enabled(self) -> bool:
        try:
            result = self._rpc("ca_is_enabled", [""])
            return bool(result.get("result", False))
        except IPAError:
            return False

    # ------------------------------------------------------------------
    # Servers / Topology
    # ------------------------------------------------------------------

    def server_find(self, criteria: str = "", **kw: Any) -> dict:
        return self._rpc("server_find", [criteria], kw)

    def topologysegment_find(self, suffix: str = "domain", **kw: Any) -> dict:
        return self._rpc("topologysegment_find", [suffix], kw)

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def batch(self, commands: list[dict]) -> dict:
        """Execute multiple commands in a single request.

        Each command dict should have: method, params (list of [args, kw]).
        """
        for cmd in commands:
            cmd.setdefault("params", [[""], {}])
            if isinstance(cmd["params"], list) and len(cmd["params"]) == 2:
                cmd["params"][1].setdefault("version", self.API_VERSION)
        return self._rpc("batch", [commands])

    # ------------------------------------------------------------------
    # Dashboard convenience
    # ------------------------------------------------------------------

    def dashboard_data(self) -> dict:
        """Fetch data needed for the dashboard in a single batch call."""
        commands = [
            {"method": "user_find", "params": [[""], {"sizelimit": 0, "pkey_only": True}]},
            {"method": "host_find", "params": [[""], {"sizelimit": 0, "pkey_only": True}]},
            {"method": "group_find", "params": [[""], {"sizelimit": 0, "pkey_only": True}]},
            {"method": "server_find", "params": [[""], {}]},
            {"method": "cert_find", "params": [[""], {"sizelimit": 0}]},
        ]
        return self.batch(commands)
