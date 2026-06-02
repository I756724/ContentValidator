"""Quick test to verify SAPterm cookies work with session-based approach."""
import requests
import json

cookie_file = "C:/Users/I756724/.sap-mcp/cookies/sapterm/sap_cookies.json"

with open(cookie_file, 'r') as f:
    data = json.load(f)

session = requests.Session()
for cookie in data['cookies']:
    session.cookies.set(
        cookie['name'], 
        cookie['value'], 
        domain=cookie['domain'], 
        path=cookie['path']
    )

print("Testing SAPterm API with session-based cookies...")
r = session.get(
    'https://lpiprod-term.ingress.prod.lp.shoot.live.k8s-hana.ondemand.com/api/termsearch/search',
    params={'term': 'service', 'sourceLanguage': 'en-US', 'pageSize': '3', 'pageNo': '1'},
    allow_redirects=True,
    timeout=10
)

print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
if 'application/json' in r.headers.get('Content-Type', ''):
    result = r.json()
    print(f"Count: {result.get('count')}")
    if result.get('matches'):
        for m in result['matches'][:3]:
            print(f"  - {m.get('sterm')}")
    print("\n✅ SAPterm cookies are WORKING!")
else:
    print(f"Content (first 200 chars): {r.text[:200]}")
    print("\n❌ SAPterm cookies NOT working (got HTML instead of JSON)")