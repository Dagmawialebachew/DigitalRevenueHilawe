import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/plan_v4_test.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find grocery table
g_idx = html.find("የሳምንት ግሮሰሪ ዝርዝር")
if g_idx == -1:
    g_idx = html.find("ግሮሰሪ")
if g_idx != -1:
    print("=== ALL GROCERY ROWS IN HTML ===")
    all_rows = re.findall(r'<tr>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>', html)
    for r in all_rows:
        item, cat, planned, buy = [re.sub(r'<[^>]+>', '', x).strip() for x in r]
        if any(w in buy for w in ("ግ", "ኪ.ግ", "ፍሬ", "kg", "g", "ጣሳ")):
            print(f"  {item} | {cat} | Planned: {planned} | Buy: {buy}")
else:
    print("Grocery section not found in HTML")
