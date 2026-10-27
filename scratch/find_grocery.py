import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

for root, dirs, files in os.walk('meal_plan'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, encoding='utf-8') as fh:
                for idx, line in enumerate(fh, 1):
                    if 'build_grocery' in line or '"grocery"' in line or "'grocery'" in line:
                        print(f"{p}:{idx}: {line.strip()}")
