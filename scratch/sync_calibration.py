import re
from meal_plan.glossary import RECIPE_GLOSSARY

with open('meal_plan/calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
current_rid = None
for line in lines:
    m = re.match(r'\s*"R(\d{3})":\s*\{', line)
    if m:
        current_rid = f"R{m.group(1)}"
    if current_rid and '"recipe_name_am":' in line:
        if current_rid in RECIPE_GLOSSARY:
            en, am = RECIPE_GLOSSARY[current_rid]
            line = re.sub(r'("recipe_name_am":\s*")[^"]+(")', rf'\g<1>{am}\g<2>', line)
    if current_rid and '"recipe_name_en":' in line:
        if current_rid in RECIPE_GLOSSARY:
            en, am = RECIPE_GLOSSARY[current_rid]
            line = re.sub(r'("recipe_name_en":\s*")[^"]+(")', rf'\g<1>{en}\g<2>', line)
    new_lines.append(line)

with open('meal_plan/calibration.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Calibration synced.")
