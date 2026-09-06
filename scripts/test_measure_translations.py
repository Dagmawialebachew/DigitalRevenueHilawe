import re
import sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")

MEASURE_DICT_AM = {
    "large bowl": "ትልቅ ጎድጓዳ ሳህን",
    "medium bowl": "መካከለኛ ጎድጓዳ ሳህን",
    "bowl": "ጎድጓዳ ሳህን",
    "large glass": "ትልቅ ብርጭቆ",
    "glass": "ብርጭቆ",
    "large cup": "ትልቅ ሲኒ",
    "cup cooked": "ሲኒ የበሰለ",
    "cups rehydrated": "ሲኒ የበሰለ/የረጠበ",
    "cup dry": "ሲኒ ጥሬ",
    "cup flour": "ሲኒ ዱቄት",
    "cup powder": "ሲኒ ዱቄት",
    "cup pieces": "ሲኒ የተከተፈ",
    "cups pieces": "ሲኒ የተከተፈ",
    "cups shredded": "ሲኒ የተከተፈ",
    "cups": "ሲኒ",
    "cup": "ሲኒ",
    "level tablespoons": "የተስተካከለ የሾርባ ማንኪያ",
    "level tablespoon": "የተስተካከለ የሾርባ ማንኪያ",
    "tablespoons": "የሾርባ ማንኪያ",
    "tablespoon": "የሾርባ ማንኪያ",
    "level teaspoon": "የተስተካከለ የሻይ ማንኪያ",
    "teaspoon": "የሻይ ማንኪያ",
    "just under 1 teaspoon": "ከ1 የሻይ ማንኪያ በትንሹ ያነሰ",
    "large slice": "ትልቅ ቁራጭ",
    "medium slice": "መካከለኛ ቁራጭ",
    "slice": "ቁራጭ",
    "slices": "ቁራጭ",
    "medium rolled piece": "መካከለኛ የተጠቀለለ እንጀራ",
    "large piece": "ትልቅ ቁራጭ",
    "medium piece": "መካከለኛ ቁራጭ",
    "piece": "ቁራጭ",
    "pieces": "ቁራጭ",
    "large fillet": "ትልቅ ቁራጭ (ፊሌ)",
    "medium fillet": "መካከለኛ ቁራጭ (ፊሌ)",
    "fillet": "ቁራጭ (ፊሌ)",
    "large thigh portion": "ትልቅ የጭን ስጋ ቁራጭ",
    "large eggs": "ትላልቅ እንቁላል",
    "large egg whites": "ትላልቅ የእንቁላል ነጭ ክፍል",
    "small drained can": "አነስተኛ የታሸገ (የተጣራ) ቆርቆሮ",
    "small can": "አነስተኛ ቆርቆሮ",
    "can": "ቆርቆሮ",
    "scoop": "ጭልፋ (ስኩፕ)",
    "small handful": "አነስተኛ ጭብጥ / እፍኝ",
    "thin cakes": "ቀጭን የሩዝ ኬክ (ክራከር)",
    "standard block": "መደበኛ የቶፉ ቁራጭ",
    "large carrot": "ትልቅ ካሮት",
    "large clove": "ትልቅ የነጭ ሽንኩርት ፍንካች",
    "large orange": "ትልቅ ብርቱካን",
    "large peach": "ትልቅ ኮክ",
    "large pepper": "ትልቅ ቃሪያ",
    "large tomato": "ትልቅ ቲማቲም",
    "medium apple": "መካከለኛ ፖም (አፕል)",
    "medium banana": "መካከለኛ ሙዝ",
    "medium bottle": "መካከለኛ ጠርሙስ",
    "medium cob": "መካከለኛ የበቆሎ ዛላ",
    "medium onion": "መካከለኛ ቀይ ሽንኩርት",
    "medium pear": "መካከለኛ ፒር (አንኮይ)",
    "medium wrap": "መካከለኛ ጥቅል ቶርቲላ",
    "medium cucumber": "መካከለኛ ኪያር",
    "large avocado": "ትልቅ አቮካዶ",
    "medium guavas": "መካከለኛ ዘይቱን",
    "medium potatoes": "መካከለኛ ድንች",
    "large dates": "ትላልቅ ቴምር",
    "palm-and-a-half": "1 ከግማሽ የእጅ መዳፍ",
    "standard portion": "መደበኛ መጠን",
    "medium serving": "መካከለኛ መጠን",
}

def translate_measure_phrase_am(phrase: str) -> str:
    cleaned = phrase.strip().lower()
    if cleaned in MEASURE_DICT_AM:
        return MEASURE_DICT_AM[cleaned]
    # Try longest match
    for k in sorted(MEASURE_DICT_AM.keys(), key=len, reverse=True):
        if k in cleaned:
            return MEASURE_DICT_AM[k]
    return cleaned

with open("meal_plan/data/hilawe_v1_3_dataset.json", "r", encoding="utf-8") as f:
    import json
    d = json.load(f)

measures = sorted(set(f.get("Familiar Measure") for f in d["foods"] if f.get("Familiar Measure")))
print(f"Testing {len(measures)} measures:")
for m in measures:
    clean = re.sub(r"^about\s+", "", m.strip(), flags=re.I)
    # Check if starts with number
    num_match = re.match(r"^(\d+(?:\.\d+)?|\d+/\d+)\s+(.+)$", clean)
    if num_match:
        qty = num_match.group(1)
        rest = num_match.group(2)
        trans = translate_measure_phrase_am(rest)
        print(f"  '{m}' -> 'በግምት {qty} {trans}'")
    else:
        trans = translate_measure_phrase_am(clean)
        print(f"  '{m}' -> 'በግምት {trans}'")
