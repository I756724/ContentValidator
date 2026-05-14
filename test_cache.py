"""Check what's in the Fiori guidelines cache"""
import sqlite3

conn = sqlite3.connect("C:/Users/cline_context/fiori-guidelines-mcp/data/cache.sqlite")
cursor = conn.cursor()

# List all cached pages
cursor.execute("SELECT key, title, category FROM cache")
rows = cursor.fetchall()
print(f"Cached pages ({len(rows)}):")
for row in rows:
    print(f"  - {row[1]} | {row[2]} | {row[0][:80]}")

# Try FTS search for "app name"
print("\n\nFTS search for 'app name':")
cursor.execute("SELECT key, title, snippet(cache_fts, 2, '>>>', '<<<', '...', 30) FROM cache_fts WHERE cache_fts MATCH 'app name'")
results = cursor.fetchall()
for r in results:
    print(f"  - {r[1]}")
    print(f"    {r[2][:200]}")

conn.close()