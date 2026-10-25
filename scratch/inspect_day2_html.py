import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/plan_v4_test.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find Day 2 card
day2_idx = html.find("ቀን 02")
if day2_idx == -1:
    day2_idx = html.find("ቀን 2")
if day2_idx == -1:
    print("Could not find Day 2")
else:
    snippet = html[day2_idx:day2_idx+4000]
    print("=== DAY 2 SNIPPET ===")
    print(snippet[:3800])
