"""
SAPterm Service - Searches SAP's official terminology database
Reads authentication cookies from:
  1. Environment variable SAPTERM_COOKIES (JSON string) - for BTP deployment
  2. Local file sap_cookies.json (managed by sap-auth-mcp) - for local development
"""
import requests
import json
import os
import time
from config import SAPTERM_API_BASE

# Cookie file location (managed by sap-auth-mcp) - used for local development
COOKIE_FILE = "C:/Users/I756724/.sap-mcp/cookies/sapterm/sap_cookies.json"

# Maximum cookie age in seconds (cookies older than this are considered expired)
MAX_COOKIE_AGE_SECONDS = 86400  # 24 hours (for BTP where cookies are set via env var)


class SAPTermService:
    """Searches SAPterm for approved terminology and German translations."""

    def __init__(self):
        self.base_url = SAPTERM_API_BASE
        self.cookie_file = COOKIE_FILE
        self._session = None

    def _get_cookie_data(self) -> dict:
        """Get cookie data from env var (BTP) or local file (dev).
        
        Priority:
        1. SAPTERM_COOKIES env var (JSON string) - for BTP deployment
        2. Local cookie file - for local development
        """
        # Try environment variable first (BTP deployment)
        env_cookies = os.environ.get("SAPTERM_COOKIES", "")
        if env_cookies:
            try:
                return json.loads(env_cookies)
            except json.JSONDecodeError:
                print("Error parsing SAPTERM_COOKIES env var")
                return {}
        
        # Fall back to local file
        try:
            if not os.path.exists(self.cookie_file):
                return {}
            with open(self.cookie_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_session(self) -> requests.Session:
        """Get or create a requests session with cookies loaded."""
        if self._session is None:
            self._session = requests.Session()
            self._load_cookies_to_session()
        return self._session

    def _load_cookies_to_session(self):
        """Load cookies into the requests session.
        
        Note: We intentionally do NOT set the domain parameter when loading cookies.
        Python's requests library adds a dot-prefix to domains which causes cookie
        matching failures. Setting cookies without domain ensures they are sent with
        every request to the SAPterm API.
        """
        try:
            data = self._get_cookie_data()
            cookies = data.get("cookies", [])
            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    self._session.cookies.set(name, value)
        except Exception as e:
            print(f"Error loading SAPterm cookies to session: {e}")

    def _are_cookies_expired(self) -> bool:
        """Check if cookies are too old based on timestamp."""
        try:
            data = self._get_cookie_data()
            if not data:
                return True
            
            timestamp = data.get("timestamp", 0)
            if timestamp == 0:
                # No timestamp means cookies were set manually (e.g. env var) - assume valid
                if os.environ.get("SAPTERM_COOKIES"):
                    return False
                return True
            
            age_seconds = (time.time() * 1000 - timestamp) / 1000
            return age_seconds > MAX_COOKIE_AGE_SECONDS
        except Exception:
            return True

    def _get_cookie_string(self) -> str:
        """Read cookies and format as cookie header string."""
        try:
            data = self._get_cookie_data()
            cookies = data.get("cookies", [])
            if not cookies:
                return ""
            
            cookie_parts = []
            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    cookie_parts.append(f"{name}={value}")
            
            return "; ".join(cookie_parts)
        except Exception as e:
            print(f"Error reading SAPterm cookies: {e}")
            return ""

    def _is_auth_redirect(self, response) -> bool:
        """Check if response is an HTML OAuth redirect (session expired)."""
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type or "html" in content_type:
            # SAPterm returns 200 with HTML containing JS redirect to OAuth when session expired
            content = response.text[:500] if response.text else ""
            if "oauth/authorize" in content or "authentication" in content.lower() or "location=" in content:
                return True
        return False

    def _make_request(self, params: dict, timeout: int = 10) -> requests.Response:
        """Make an authenticated request to SAPterm using session with cookies."""
        session = self._get_session()
        response = session.get(
            f"{self.base_url}/api/termsearch/search",
            params=params,
            timeout=timeout,
            allow_redirects=True
        )
        return response

    def is_available(self) -> bool:
        """Check if SAPterm cookies exist and API is accessible."""
        # First check if cookies are too old
        if self._are_cookies_expired():
            self._session = None  # Reset session to reload cookies
            return False
        
        cookie = self._get_cookie_string()
        if not cookie:
            return False
        try:
            response = self._make_request(
                params={"term": "test", "pageSize": "1", "pageNo": "1", "sourceLanguage": "en-US"},
                timeout=5
            )
            if response.status_code != 200:
                return False
            if self._is_auth_redirect(response):
                return False
            return True
        except Exception:
            return False

    def search_term(self, term: str) -> dict:
        """
        Search SAPterm for a term with German translation.
        
        API Response format:
        {
            "count": N,
            "matches": [
                {
                    "sterm": "Service Order",
                    "scomponent": "AP-SVO",
                    "sglossary": "definition...",
                    "sstatus": "Released",
                    "sobjtyp": "Main Entry",
                    "tlang": "deDE - German",
                    "tterm": "Serviceauftrag"  (if targetLanguage specified)
                }
            ]
        }
        """
        cookie = self._get_cookie_string()
        if not cookie:
            return {"found": False, "results": [], "error": "SAPterm not authenticated. Run sap_authenticate for SAPterm."}

        try:
            response = self._make_request(params={
                "term": term,
                "sourceLanguage": "en-US",
                "targetLanguage": "de-DE",
                "status": "Released",
                "searchMethod": "EXACT",
                "objectType": "Main_Entry",
                "pageSize": "20",
                "pageNo": "1"
            })

            if response.status_code == 302 or response.status_code == 401:
                return {"found": False, "results": [], "error": "SAPterm cookie expired. Re-authenticate with sap-auth-mcp."}

            # Check for HTML OAuth redirect (200 status but session expired)
            if self._is_auth_redirect(response):
                self._session = None  # Reset session
                return {"found": False, "results": [], "error": "SAPterm session expired (OAuth redirect detected). Re-authenticate with sap-auth-mcp."}

            if response.status_code == 400:
                # Try without some filters
                response = self._make_request(params={
                    "term": term,
                    "sourceLanguage": "en-US",
                    "targetLanguage": "de-DE",
                    "searchMethod": "STARTS_WITH",
                    "pageSize": "20",
                    "pageNo": "1"
                })

            if response.status_code != 200:
                return {"found": False, "results": [], "error": f"SAPterm returned status {response.status_code}"}

            data = response.json()
            results = []

            matches = data.get("matches", [])
            for entry in matches:
                result = {
                    "term": entry.get("sterm", term),
                    "german": entry.get("tterm", ""),
                    "definition": entry.get("sglossary", ""),
                    "component": entry.get("scomponent", ""),
                    "status": entry.get("sstatus", "Released")
                }
                results.append(result)

            return {
                "found": len(results) > 0,
                "results": results,
                "total_count": data.get("count", 0),
                "error": None
            }

        except requests.Timeout:
            return {"found": False, "results": [], "error": "SAPterm timeout"}
        except json.JSONDecodeError:
            return {"found": False, "results": [], "error": "Invalid response from SAPterm API"}
        except Exception as e:
            return {"found": False, "results": [], "error": str(e)}

    def search_similar(self, term: str) -> dict:
        """Search SAPterm with STARTS_WITH to find similar/related terms."""
        cookie = self._get_cookie_string()
        if not cookie:
            return {"results": [], "error": "SAPterm not authenticated"}

        try:
            response = self._make_request(params={
                "term": term,
                "sourceLanguage": "en-US",
                "targetLanguage": "de-DE",
                "searchMethod": "STARTS_WITH",
                "pageSize": "10",
                "pageNo": "1"
            })

            if response.status_code != 200:
                return {"results": [], "error": "SAPterm search failed"}

            # Check for HTML OAuth redirect (200 status but session expired)
            if self._is_auth_redirect(response):
                self._session = None  # Reset session
                return {"results": [], "error": "SAPterm session expired. Re-authenticate with sap-auth-mcp."}

            data = response.json()
            results = []

            matches = data.get("matches", [])
            for entry in matches:
                results.append({
                    "term": entry.get("sterm", ""),
                    "german": entry.get("tterm", ""),
                    "component": entry.get("scomponent", "")
                })

            return {"results": results, "error": None}

        except Exception as e:
            return {"results": [], "error": str(e)}

    def get_status(self) -> dict:
        """Get SAPterm connection status."""
        cookie = self._get_cookie_string()
        if not cookie:
            return {"status": "not_configured", "message": "No SAPterm cookies found. Authenticate with sap-auth-mcp."}
        
        if self.is_available():
            return {"status": "connected", "message": "SAPterm connected"}
        else:
            return {"status": "expired", "message": "Cookie expired - re-authenticate with sap-auth-mcp"}