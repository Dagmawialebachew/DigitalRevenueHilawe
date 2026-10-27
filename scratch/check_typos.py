import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from pypdf import PdfReader
import re

reader = PdfReader("Yohannes-7days-plan-V2.pdf")
print("=== CHECKING TYPOS AND STRINGS IN V2 PDF ===")

full_text = ""
for i, page in enumerate(reader.pages):
    t = page.extract_text()
    full_text += f"\n--- Page {i+1} ---\n" + t
    for typo in ["dimer", "gig keal", "about 1 approx", "about i approx", "iii g", "cooked broccoli  g"]:
        if typo in t.lower():
            print(f"[FOUND TYPO] '{typo}' on Page {i+1}!")

# Check Day 1 swaps
print("\n--- DAY 1 TEXT SNIPPET ---")
print(reader.pages[4].extract_text()[:1200])

# Check Day 4 Dinner Broccoli
print("\n--- DAY 4 TEXT SNIPPET ---")
print(reader.pages[7].extract_text()[:1200])
