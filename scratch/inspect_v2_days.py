import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from pypdf import PdfReader

reader = PdfReader("Yohannes-7days-plan-V2.pdf")
print("=== EXTRACTING DAYS FROM Yohannes-7days-plan-V2.pdf ===")
for p_idx in range(4, 11):
    day_num = p_idx - 3
    text = reader.pages[p_idx].extract_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    header = lines[0] if len(lines) > 0 else ""
    day_title = lines[1] if len(lines) > 1 else ""
    print(f"\n--- PAGE {p_idx+1} (DAY {day_num}) ---")
    for l in lines[:15]:
        print(" ", l)
