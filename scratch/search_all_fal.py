import os
from pathlib import Path

root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
found = []
for p in root.rglob("*"):
    if p.is_file() and p.suffix in (".py", ".json", ".html", ".sql", ".md", ".txt"):
        try:
            txt = p.read_text(encoding="utf-8")
            if "ፋል" in txt:
                found.append(str(p))
                print(f"Found in {p}")
        except Exception:
            try:
                txt = p.read_text(encoding="latin-1")
                if "ፋል" in txt:
                    found.append(str(p))
                    print(f"Found (latin1) in {p}")
            except Exception:
                pass
print(f"Total files found: {len(found)}")
