import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from pypdf import PdfReader

repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
pdf_path = repo_root / "Yohannes-7days-plan-FINAL.pdf"

if not pdf_path.exists():
    print(f"ERROR: {pdf_path} does not exist!")
    sys.exit(1)

reader = PdfReader(str(pdf_path))
print(f"Total pages: {len(reader.pages)}")

print("\n--- PAGE 1 (Cover) ---")
print(reader.pages[0].extract_text()[:400])

print("\n--- PAGE 2 (Glance) ---")
print(reader.pages[1].extract_text()[:400])

print("\n--- PAGE 5 (Day 1) ---")
print(reader.pages[4].extract_text()[:600])

print("\n--- PAGE 6 (Day 2) ---")
print(reader.pages[5].extract_text()[:600])

print("\n--- PAGE 13 (Grocery P1) ---")
print(reader.pages[12].extract_text()[:600])

print("\n--- PAGE 14 (Grocery P2) ---")
print(reader.pages[13].extract_text()[:600])
