import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from pypdf import PdfReader
import re

reader = PdfReader("Yohannes-7days-plan-V2.pdf")
print("=== SEARCHING FOR RICE CAKES IN V2 PDF ===")
found = False
for i, page in enumerate(reader.pages):
    text = page.extract_text()
    if "rice cake" in text.lower():
        found = True
        print(f"\nPage {i+1}:")
        for line in text.split("\n"):
            if "rice cake" in line.lower() or "cake" in line.lower():
                print("  ", line.strip())

if not found:
    print("No rice cakes found in V2 PDF!")
