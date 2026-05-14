"""
SAPterm Service - Searches SAP's official terminology database
Reads authentication cookies from sap_cookies.json (managed by sap-auth-mcp)
"""
import requests
import json
import os
from config import SAPTERM_API_BASE

# Cookie file location (managed by sap-auth-mcp)
COOKIE_FILE = "C:/Users/I756724/.sap-mcp/cookies/sapterm/sap_cookies.json"


class SAPTermService:
    """Searches SAPterm for approved terminology and German translations."""

    def __init__(self):
        self.base_url = SAPTERM_API_BASE
        self.cookie_file = COOKIE_FILE

    def _get_cookie_string(self) -> str:
        """Read cookies from sap_cookies.json and format as cookie header string."""
        try:
            if not os.path.exists(self.cookie_file):
                return ""
            
            with open(self.cookie_file, 'r') as f:
                data = json.load(f)
            
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

    def is_available(self) -> bool:
        """Check if SAPterm cookies exist and API is accessible."""
        cookie = self._get_cookie_string()
        if not cookie:
            return False
        try:
            response = requests.get(
                f"{self.base_url}/api/termsearch/search",
                params={"term": "test", "pageSize": "1", "pageNo": "1", "sourceLanguage": "en-US"},
                headers={"Cookie": cookie},
                timeout=5,
                allow_redirects=False
            )
            return response.status_code == 200
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
            response = requests.get(
                f"{self.base_url}/api/termsearch/search",
                params={
                    "term": term,
                    "sourceLanguage": "en-US",
                    "targetLanguage": "de-DE",
                    "status": "Released",
                    "searchMethod": "EXACT",
                    "objectType": "Main_Entry",
                    "pageSize": "20",
                    "pageNo": "1"
                },
                headers={"Cookie": cookie},
                timeout=10,
                allow_redirects=False
            )

            if response.status_code == 302 or response.status_code == 401:
                return {"found": False, "results": [], "error": "SAPterm cookie expired. Re-authenticate with sap-auth-mcp."}

            if response.status_code == 400:
                # Try without some filters
                response = requests.get(
                    f"{self.base_url}/api/termsearch/search",
                    params={
                        "term": term,
                        "sourceLanguage": "en-US",
                        "targetLanguage": "de-DE",
                        "searchMethod": "STARTS_WITH",
                        "pageSize": "20",
                        "pageNo": "1"
                    },
                    headers={"Cookie": cookie},
                    timeout=10,
                    allow_redirects=False
                )

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
            response = requests.get(
                f"{self.base_url}/api/termsearch/search",
                params={
                    "term": term,
                    "sourceLanguage": "en-US",
                    "targetLanguage": "de-DE",
                    "searchMethod": "STARTS_WITH",
                    "pageSize": "10",
                    "pageNo": "1"
                },
                headers={"Cookie": cookie},
                timeout=10,
                allow_redirects=False
            )

            if response.status_code != 200:
                return {"results": [], "error": "SAPterm search failed"}

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