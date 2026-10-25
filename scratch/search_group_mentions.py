import os, json, sys

sys.stdout.reconfigure(encoding='utf-8')
brain_dir = r"C:\Users\kiruk\.gemini\antigravity-ide\brain"

for entry in os.scandir(brain_dir):
    if entry.is_dir():
        t_path = os.path.join(entry.path, ".system_generated", "logs", "transcript.jsonl")
        if os.path.exists(t_path):
            try:
                with open(t_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        low = line.lower()
                        if "dedicated group" in low or "meal-plan group" in low or "meal plan group" in low:
                            try:
                                d = json.loads(line)
                                if d.get("type") == "USER_INPUT":
                                    print(f"Session {entry.name}: {d.get('content')[:300]}\n")
                            except:
                                pass
            except:
                pass
