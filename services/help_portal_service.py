"""
SAP Help Portal Service - Searches help.sap.com for term usage and documentation
Public API - no authentication needed
"""
import requests


class HelpPortalService:
    """Searches SAP Help Portal for term usage in published documentation."""

    BASE_URL = "https://help.sap.com"

    def search(self, query: str, limit: int = 5) -> dict:
        """
        Search SAP Help Portal.
        
        Returns:
            {
                "results": [{"title": str, "url": str, "description": str}],
                "error": str or None
            }
        """
        try:
            # Help Portal has a search API
            response = requests.get(
                f"{self.BASE_URL}/http.svc/search",
                params={
                    "q": query,
                    "language": "en",
                    "state": "PRODUCTION",
                    "top": limit
                },
                headers={"Accept": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                results = []
                
                items = data.get("d", {}).get("results", data.get("results", []))
                if isinstance(items, list):
                    for item in items:
                        results.append({
                            "title": item.get("Title", item.get("title", "")),
                            "url": item.get("Url", item.get("url", "")),
                            "description": item.get("Description", item.get("description", ""))[:150]
                        })
                
                return {"results": results, "error": None}
            else:
                # Try alternative search endpoint
                return self._search_alternative(query, limit)

        except Exception as e:
            return {"results": [], "error": str(e)}

    def _search_alternative(self, query: str, limit: int) -> dict:
        """Alternative search using help.sap.com viewer search."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/docs/search",
                params={"q": query, "locale": "en-US"},
                headers={"Accept": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    results = []
                    for item in data.get("results", [])[:limit]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("snippet", "")[:150]
                        })
                    return {"results": results, "error": None}
                except Exception:
                    pass
            
            return {"results": [], "error": f"Help Portal returned {response.status_code}"}
        except Exception as e:
            return {"results": [], "error": str(e)}

    def search_term_usage(self, term: str) -> dict:
        """Search help portal for how a specific term is used in SAP documentation."""
        return self.search(f'"{term}" SAP', limit=3)

    def is_available(self) -> bool:
        """Help Portal is always available (public)."""
        return True