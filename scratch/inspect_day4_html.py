import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/plan_v4_test.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find Day 4 card
day4_idx = html.find("ቀን 04")
if day4_idx == -1:
    day4_idx = html.find("ቀን 4")
if day4_idx == -1:
    print("Could not find Day 4")
else:
    snippet = html[day4_idx:day4_idx+3000]
    print("=== DAY 4 SNIPPET ===")
    print(snippet[:1500])
