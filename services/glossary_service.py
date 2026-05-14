"""
SAP Glossary Service - Searches help.sap.com/glossary for term definitions
"""
import requests


class GlossaryService:
    """Searches SAP Help Portal Glossary for term definitions."""

    BASE_URL = "https://help.sap.com/glossary"

    def search_term(self, term: str, component: str = "") -> dict:
        """
        Search SAP Glossary for a term.
        
        Args:
            term: The term to search
            component: Optional SAP component (e.g., "CRM-BTX-SVO")
            
        Returns:
            {
                "found": bool,
                "entries": [{"term": str, "definition": str, "component": str}],
                "error": str or None
            }
        """
        try:
            params = {"locale": "en-US", "q": term}
            if component:
                url = f"{self.BASE_URL}/{component}/{term}"
            else:
                url = self.BASE_URL
                
            response = requests.get(
                url,
                params=params,
                timeout=10,
                headers={"Accept": "application/json"}
            )

            if response.status_code != 200:
                # Try HTML scraping approach as fallback
                return self._search_html(term)

            data = response.json()
            entries = []
            
            if isinstance(data, list):
                for item in data:
                    entries.append({
                        "term": item.get("term", term),
                        "definition": item.get("definition", ""),
                        "component": item.get("component", "")
                    })
            elif isinstance(data, dict):
                if "entries" in data:
                    for item in data["entries"]:
                        entries.append({
                            "term": item.get("term", term),
                            "definition": item.get("definition", ""),
                            "component": item.get("component", "")
                        })

            return {
                "found": len(entries) > 0,
                "entries": entries,
                "error": None
            }

        except Exception as e:
            return {"found": False, "entries": [], "error": str(e)}

    def _search_html(self, term: str) -> dict:
        """Fallback: search glossary via HTML page."""
        try:
            response = requests.get(
                f"{self.BASE_URL}",
                params={"locale": "en-US", "q": term},
                timeout=10
            )
            
            if response.status_code == 200 and term.lower() in response.text.lower():
                return {
                    "found": True,
                    "entries": [{"term": term, "definition": "Found in SAP Glossary (check link for details)", "component": ""}],
                    "error": None,
                    "link": f"{self.BASE_URL}?locale=en-US&q={term}"
                }
            
            return {"found": False, "entries": [], "error": None}
            
        except Exception as e:
            return {"found": False, "entries": [], "error": str(e)}