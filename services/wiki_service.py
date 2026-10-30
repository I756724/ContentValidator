"""
SAP Wiki Service - Searches SAP internal wiki (Confluence) for UA guidelines.

Cookie source priority:
  1. Claude Code MCP plugin (C:/Users/.../AppData/Local/Temp/mcp-wiki/wiki.one.int.sap.json)
     - Format: {"cookies": "JSESSIONID=...; ...", "timestamp": ..., "domain": "..."}
     - Managed and refreshed by the mcp-wiki plugin; no manual maintenance needed.
  2. Legacy cookie file (C:/Users/I756724/.sap-mcp/cookies/wiki/sap_cookies.json)
     - Format: {"cookies": [{"name": "...", "value": "..."}], "timestamp": <ms>}
     - Requires manual refresh every 24 hours.
"""
import requests
import json
import os
import re
import time

WIKI_BASE = "https://wiki.one.int.sap"

# MCP plugin cookie file — written and refreshed by the Claude Code mcp-wiki plugin
MCP_COOKIE_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", "C:/Users/I756724/AppData/Local"),
    "Temp", "mcp-wiki", "wiki.one.int.sap.json"
)

# Legacy cookie file — manually maintained
LEGACY_COOKIE_FILE = "C:/Users/I756724/.sap-mcp/cookies/wiki/sap_cookies.json"

# Status is cached for 5 minutes to avoid a live HTTP test on every poll
_STATUS_CACHE_TTL = 300


class WikiService:
    """Searches SAP Wiki (Confluence) for UA guidelines and style rules."""

    def __init__(self):
        self.base_url = WIKI_BASE
        self._status_cache = None
        self._status_cache_ts = 0.0

    # ── Cookie loading ────────────────────────────────────────────────────────

    def _load_cookie_string(self) -> str:
        """Return a ready-to-use Cookie header string, or empty string if unavailable."""
        # 1. MCP plugin cookie (string format — already formatted for HTTP header)
        try:
            if os.path.exists(MCP_COOKIE_FILE):
                with open(MCP_COOKIE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                cookies = data.get("cookies", "")
                if isinstance(cookies, str) and cookies.strip():
                    return cookies.strip()
        except Exception:
            pass

        # 2. Legacy cookie file (list-of-objects format, 24-hour expiry)
        try:
            if os.path.exists(LEGACY_COOKIE_FILE):
                with open(LEGACY_COOKIE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                cookies = data.get("cookies", [])
                if not isinstance(cookies, list):
                    return ""
                ts = data.get("timestamp", 0)
                if ts > 0:
                    age_secs = (time.time() * 1000 - ts) / 1000
                    if age_secs > 86400:
                        return ""
                return "; ".join(
                    f"{c['name']}={c['value']}"
                    for c in cookies
                    if c.get("name") and c.get("value")
                )
        except Exception:
            pass

        return ""

    # ── Auth detection ────────────────────────────────────────────────────────

    def _is_auth_redirect(self, response: requests.Response) -> bool:
        ct = response.headers.get("Content-Type", "")
        if "text/html" in ct:
            snippet = (response.text or "")[:500].lower()
            return any(k in snippet for k in ("login", "oauth", "authenticate", "accounts.sap"))
        return False

    def _quick_auth_test(self, cookie: str) -> bool:
        """Ping the Confluence user API to verify the cookie is still valid."""
        try:
            r = requests.get(
                f"{self.base_url}/wiki/rest/api/user/current",
                headers={"Cookie": cookie, "Accept": "application/json"},
                timeout=5,
                allow_redirects=False
            )
            return r.status_code == 200 and not self._is_auth_redirect(r)
        except Exception:
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return bool(self._load_cookie_string())

    def get_status(self) -> dict:
        """Live auth test, result cached for 5 minutes."""
        now = time.time()
        if self._status_cache and now - self._status_cache_ts < _STATUS_CACHE_TTL:
            return self._status_cache

        cookie = self._load_cookie_string()
        if not cookie:
            result = {"status": "not_configured",
                      "message": "No Wiki cookies. Authenticate via mcp-wiki or sap-auth-mcp."}
        elif self._quick_auth_test(cookie):
            result = {"status": "connected", "message": "SAP Wiki connected"}
        else:
            result = {"status": "expired",
                      "message": "Wiki cookies expired. Re-authenticate via browser or mcp-wiki plugin."}

        self._status_cache = result
        self._status_cache_ts = now
        return result

    def search(self, query: str, limit: int = 5) -> dict:
        """
        Search SAP Wiki via Confluence REST API.

        Returns:
            {"results": [{"title", "url", "excerpt"}], "error": str or None}
        """
        cookie = self._load_cookie_string()
        if not cookie:
            return {"results": [], "error": "Wiki not authenticated."}

        try:
            response = requests.get(
                f"{self.base_url}/wiki/rest/api/content/search",
                params={
                    "cql": f'type=page AND text~"{query}"',
                    "limit": limit,
                    "expand": "body.view"
                },
                headers={"Cookie": cookie, "Accept": "application/json"},
                timeout=10,
                allow_redirects=False
            )

            if response.status_code == 401:
                self._status_cache = None  # invalidate cache
                return {"results": [], "error": "Wiki session expired (401)."}

            if response.status_code in (301, 302, 303, 307):
                self._status_cache = None
                return {"results": [], "error": "Wiki session expired (redirect)."}

            if self._is_auth_redirect(response):
                self._status_cache = None
                return {"results": [], "error": "Wiki returned login page."}

            if response.status_code != 200:
                return {"results": [], "error": f"Wiki returned HTTP {response.status_code}"}

            data = response.json()
            results = []
            for item in data.get("results", []):
                title = item.get("title", "")
                page_id = item.get("id", "")
                url = f"{self.base_url}/wiki/pages/viewpage.action?pageId={page_id}"
                body = item.get("body", {}).get("view", {}).get("value", "")
                excerpt = re.sub(r"<[^>]+>", "", body)[:200]
                results.append({"title": title, "url": url, "excerpt": excerpt})

            return {"results": results, "error": None}

        except requests.Timeout:
            return {"results": [], "error": "Wiki request timed out (10s)"}
        except Exception as e:
            return {"results": [], "error": str(e)}

    def search_guidelines(self, term: str, element_type: str = "") -> dict:
        """Search wiki for UA guidelines relevant to a term or element type."""
        query = f"UA guidelines {element_type} {term}" if element_type else f"UA guidelines {term}"
        return self.search(query, limit=3)
