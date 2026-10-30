"""
SAP Translation Service - Real German translation via SAP MT Portal (mtportal.int.sap)
API pattern sourced from the official SAP Translation MCP (github.tools.sap/I576460/sap-translation-mcp)

Cookie file: C:/Users/I756724/.sap-mcp/cookies/mtportal/sap_cookies.json
Same schema as SAPterm/Wiki cookies (exported via sap-auth-mcp or browser extension).
"""
import requests
import json
import os
import time

MT_PORTAL_BASE = os.environ.get("SAP_TRANSLATION_BASE_URL", "https://mtportal.int.sap")
COOKIE_FILE = "C:/Users/I756724/.sap-mcp/cookies/mtportal/sap_cookies.json"
MAX_COOKIE_AGE_SECONDS = 86400  # 24 hours


class TranslationService:
    """
    Calls SAP MT Portal for real German translations.
    Requires SSO cookies for mtportal.int.sap (SAP VPN required).
    Falls back gracefully when unavailable.
    """

    def __init__(self):
        self.base_url = MT_PORTAL_BASE.rstrip("/")
        self.cookie_file = os.environ.get("SAP_TRANSLATION_COOKIE_FILE", COOKIE_FILE)
        self._csrf_token = None
        self._session = None

    def _get_cookie_data(self) -> dict:
        """Load cookie data from environment (BTP) or local file (dev)."""
        env_cookies = os.environ.get("MTPORTAL_COOKIES", "")
        if env_cookies:
            try:
                return json.loads(env_cookies)
            except json.JSONDecodeError:
                return {}
        try:
            if not os.path.exists(self.cookie_file):
                return {}
            with open(self.cookie_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_cookie_string(self) -> str:
        """Format cookies as a Cookie header string."""
        data = self._get_cookie_data()
        cookies = data.get("cookies", [])
        if not cookies:
            return ""
        return "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value"))

    def _are_cookies_expired(self) -> bool:
        """Check if stored cookies are older than 24 hours."""
        data = self._get_cookie_data()
        if not data:
            return True
        timestamp = data.get("timestamp", 0)
        if timestamp == 0:
            return bool(not os.environ.get("MTPORTAL_COOKIES"))
        age = (time.time() * 1000 - timestamp) / 1000
        return age > MAX_COOKIE_AGE_SECONDS

    def _get_session(self) -> requests.Session:
        """Build a requests.Session with cookies and User-Agent set."""
        session = requests.Session()
        cookie_string = self._get_cookie_string()
        if cookie_string:
            session.headers.update({
                "Cookie": cookie_string,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Application": "ua-content-validator",
            })
        return session

    def _fetch_csrf_token(self, session: requests.Session) -> str:
        """Fetch CSRF token from MT Portal (same pattern as Translation MCP)."""
        try:
            response = session.get(
                f"{self.base_url}/api/v1/languages",
                headers={"X-CSRF-Token": "Fetch"},
                timeout=10,
                allow_redirects=False
            )
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type:
                return ""
            token = response.headers.get("x-csrf-token", "")
            return token
        except Exception:
            return ""

    def _is_html_response(self, response: requests.Response) -> bool:
        """Detect if the portal redirected to a login page."""
        ct = response.headers.get("Content-Type", "")
        return "text/html" in ct

    def is_available(self) -> bool:
        """Check if MT Portal cookies exist and are still fresh."""
        if self._are_cookies_expired():
            return False
        return bool(self._get_cookie_string())

    def translate(self, text: str, target_language: str = "de-DE", source_language: str = "en-US") -> dict:
        """
        Translate text using SAP MT Portal.

        Returns:
            {
                "translated": str or None,
                "source_language": str,
                "target_language": str,
                "error": str or None,
                "available": bool
            }
        """
        cookie = self._get_cookie_string()
        if not cookie:
            return {
                "translated": None,
                "source_language": source_language,
                "target_language": target_language,
                "error": "MT Portal not authenticated. Export cookies from mtportal.int.sap to C:/Users/I756724/.sap-mcp/cookies/mtportal/sap_cookies.json",
                "available": False
            }

        if self._are_cookies_expired():
            return {
                "translated": None,
                "source_language": source_language,
                "target_language": target_language,
                "error": "MT Portal cookies expired. Re-authenticate via browser.",
                "available": False
            }

        session = self._get_session()

        try:
            # Step 1: Get CSRF token
            csrf_token = self._fetch_csrf_token(session)

            # Step 2: POST translation request as multipart form (plain text)
            params = {"targetLanguage": target_language, "sourceLanguage": source_language}
            boundary = f"----MCPBoundary{int(time.time() * 1000)}"
            body = (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"input.txt\"\r\n"
                f"Content-Type: text/plain\r\n"
                f"\r\n"
                f"{text}\r\n"
                f"--{boundary}--\r\n"
            )

            headers = {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }
            if csrf_token:
                headers["X-CSRF-Token"] = csrf_token

            response = session.post(
                f"{self.base_url}/api/v1/translation",
                params=params,
                data=body.encode("utf-8"),
                headers=headers,
                timeout=30,
                allow_redirects=False
            )

            if response.status_code in (301, 302, 303, 307, 401):
                return {
                    "translated": None,
                    "source_language": source_language,
                    "target_language": target_language,
                    "error": "MT Portal session expired. Re-authenticate via browser.",
                    "available": False
                }

            if self._is_html_response(response):
                return {
                    "translated": None,
                    "source_language": source_language,
                    "target_language": target_language,
                    "error": "MT Portal returned login page. Re-authenticate via browser.",
                    "available": False
                }

            if response.status_code == 403:
                # CSRF mismatch - retry once with fresh token
                self._csrf_token = None
                session2 = self._get_session()
                csrf_token2 = self._fetch_csrf_token(session2)
                headers["X-CSRF-Token"] = csrf_token2
                response = session2.post(
                    f"{self.base_url}/api/v1/translation",
                    params=params,
                    data=body.encode("utf-8"),
                    headers=headers,
                    timeout=30,
                    allow_redirects=False
                )

            if response.status_code != 200:
                return {
                    "translated": None,
                    "source_language": source_language,
                    "target_language": target_language,
                    "error": f"MT Portal returned HTTP {response.status_code}",
                    "available": True
                }

            translated_text = response.text.strip()
            if not translated_text:
                return {
                    "translated": None,
                    "source_language": source_language,
                    "target_language": target_language,
                    "error": "MT Portal returned empty translation",
                    "available": True
                }

            return {
                "translated": translated_text,
                "source_language": source_language,
                "target_language": target_language,
                "error": None,
                "available": True
            }

        except requests.Timeout:
            return {
                "translated": None,
                "source_language": source_language,
                "target_language": target_language,
                "error": "MT Portal timeout (30s). Check VPN connection.",
                "available": True
            }
        except Exception as e:
            return {
                "translated": None,
                "source_language": source_language,
                "target_language": target_language,
                "error": str(e),
                "available": True
            }

    def get_status(self) -> dict:
        """Return service status for the /status endpoint."""
        cookie = self._get_cookie_string()
        if not cookie:
            return {"status": "not_configured", "message": "No MT Portal cookies. Authenticate via mtportal.int.sap."}
        if self._are_cookies_expired():
            return {"status": "expired", "message": "MT Portal cookies expired. Re-authenticate."}
        return {"status": "connected", "message": "SAP MT Portal connected"}
