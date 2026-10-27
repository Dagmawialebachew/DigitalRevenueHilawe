import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from pypdf import PdfReader

for target_name in ["Yohannes-7days-plan-FINAL-PERFECT.pdf", "Yohannes-7days-plan-V2.pdf"]:
    pdf_path = Path(target_name)
    if not pdf_path.exists():
        continue
    reader = PdfReader(str(pdf_path))
    print(f"\n=======================================================")
    print(f"VERIFYING: {target_name} ({len(reader.pages)} pages)")
    print(f"=======================================================")
    
    print("\n--- PAGE 1 (Cover Goal) ---")
    p1 = reader.pages[0].extract_text()
    for l in p1.split("\n"):
        if any(k in l.lower() for k in ["goal", "muscle gain", "prepared for", "duration"]):
            print(" ", l.strip())

    print("\n--- PAGE 2 (Glance Metrics) ---")
    p2 = reader.pages[1].extract_text()
    for l in p2.split("\n"):
        if any(k in l.lower() for k in ["current weight", "target weight", "phase 1", "daily energy", "protein"]):
            print(" ", l.strip())

    print("\n--- PAGE 5 (Day 1 Meals & Rice Cakes) ---")
    p5 = reader.pages[4].extract_text()
    for l in p5.split("\n"):
        if any(k in l.lower() for k in ["day 01", "calories", "protein", "rice cake", "tuna pasta", "dimer", "dinner"]):
            print(" ", l.strip())

    print("\n--- PAGE 13 (Grocery Eggs & Packaging) ---")
    p13 = reader.pages[12].extract_text()
    for l in p13.split("\n"):
        if any(k in l.lower() for k in ["egg", "milk", "olive", "sunflower", "tuna", "chicken"]):
            print(" ", l.strip())
