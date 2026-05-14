"""
SAP Wiki Service - Searches SAP internal wiki (Confluence) for guidelines
Reads authentication cookies from sap_cookies.json
"""
import requests
import json
import os

WIKI_BASE = "https://wiki.one.int.sap"
COOKIE_FILE = "C:/Users/I756724/.sap-mcp/cookies/wiki/sap_cookies.json"


class WikiService:
    """Searches SAP Wiki for guidelines and style rules."""

    def __init__(self):
        self.base_url = WIKI_BASE
        self.cookie_file = COOKIE_FILE

    def _get_cookie_string(self) -> str:
        """Read cookies from sap_cookies.json."""
        try:
            if not os.path.exists(self.cookie_file):
                return ""
            with open(self.cookie_file, 'r') as f:
                data = json.load(f)
            cookies = data.get("cookies", [])
            return "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value"))
        except Exception:
            return ""

    def is_available(self) -> bool:
        """Check if wiki cookies exist."""
        return bool(self._get_cookie_string())

    def search(self, query: str, limit: int = 5) -> dict:
        """
        Search SAP Wiki using Confluence REST API.
        
        Returns:
            {
                "results": [{"title": str, "url": str, "excerpt": str}],
                "error": str or None
            }
        """
        cookie = self._get_cookie_string()
        if not cookie:
            return {"results": [], "error": "Wiki not authenticated"}

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

            if response.status_code != 200:
                return {"results": [], "error": f"Wiki returned {response.status_code}"}

            data = response.json()
            results = []

            for item in data.get("results", []):
                title = item.get("title", "")
                page_id = item.get("id", "")
                url = f"{self.base_url}/wiki/pages/viewpage.action?pageId={page_id}"
                
                # Get excerpt from body
                body = item.get("body", {}).get("view", {}).get("value", "")
                # Strip HTML tags for excerpt
                import re
                excerpt = re.sub(r'<[^>]+>', '', body)[:200]

                results.append({
                    "title": title,
                    "url": url,
                    "excerpt": excerpt
                })

            return {"results": results, "error": None}

        except Exception as e:
            return {"results": [], "error": str(e)}

    def search_guidelines(self, term: str, element_type: str = "") -> dict:
        """Search wiki specifically for UI text guidelines related to a term."""
        query = f"UA guidelines {element_type} {term}" if element_type else f"UA guidelines {term}"
        return self.search(query, limit=3)