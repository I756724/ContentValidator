"""Test SAPterm API connection with cookies from sap_cookies.json"""
import json
import requests

COOKIE_FILE = "C:/Users/I756724/.sap-mcp/cookies/sapterm/sap_cookies.json"
API_BASE = "https://lpiprod-term.ingress.prod.lp.shoot.live.k8s-hana.ondemand.com"

# Read cookies
with open(COOKIE_FILE) as f:
    data = json.load(f)

cookies = data.get("cookies", [])
cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value"))

print(f"Cookie count: {len(cookies)}")
print(f"Cookie string length: {len(cookie_str)}")
print(f"First 100 chars: {cookie_str[:100]}...")
print()

# Test API call
print("Testing SAPterm API...")
r = requests.get(
    f"{API_BASE}/api/termsearch/search",
    params={
        "term": "service order",
        "sourceLanguage": "en-US",
        "searchMethod": "STARTS_WITH",
        "pageSize": "5",
        "pageNo": "1"
    },
    headers={"Cookie": cookie_str},
    timeout=10,
    allow_redirects=False
)

print(f"Status: {r.status_code}")
print(f"Response (first 500 chars): {r.text[:500]}")