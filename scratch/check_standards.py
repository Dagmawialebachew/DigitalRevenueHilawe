import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/plan_v4_test.html", "r", encoding="utf-8") as f:
    html = f.read()

injera_std = "1 መካከለኛ ጥቅል እንጀራ በግምት 120 ግራም ነው።"
water_std = "2.5 ሊትር / ቀን (10 መካከለኛ ብርጭቆዎች — እያንዳንዳቸው 250 ሚ.ሊ)"

print(f"Injera standard in HTML: {injera_std in html}")
print(f"Water standard in HTML: {water_std in html}")

# Count occurrences of water_std
print(f"Water standard occurrences: {html.count(water_std)}")
