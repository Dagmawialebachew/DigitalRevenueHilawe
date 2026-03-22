STRINGS = {
    "EN": {
        "ask_gender": (
            "📍 *Step 1/5 — Bio Profile* 🧬\n"
            "`▰▱▱▱▱` 20%\n\n"
            "First, I need to know who I'm training. Identify your gender:"
        ),
        "ask_goal": (
            "📍 *Step 2/5 — Objective* 🎯\n"
            "`▰▰▱▱▱` 40%\n\n"
            "What is your primary goal? Be specific about what you want to achieve:"
        ),
     "ask_level": (
    "📍 *Step 3 of 5 — Experience Baseline* ⚖️\n"
    "`▰▰▰▱▱` 60%\n\n"
    "Be real with me. Where are you actually at?\n\n"
    "• *Beginner:* Just starting or restarting.\n"
    "• *Intermediate:* Consistent, but results have stalled.\n"
    "• *Glute Focused:* Specifically targeting lower body growth.\n"
    "• *Advanced:* Pushing for elite performance."
),
        "ask_obstacle": (
            "📍 *Step 4/5 — Obstacles* 🚧\n"
            "`▰▰▰▰▱` 80%\n\n"
            "What has been your biggest struggle? Tell me what's holding you back:"
        ),
        "ask_freq": (
            "📍 *Step 5/5 — Commitment* ⏳\n"
            "`▰▰▰▰▰` 100%\n\n"
            "Consistency is everything. How many days a week can you honestly give me?"
        ),
        "analysis_start": (
            "📍 *Processing Strategy* ⚙️\n\n"
            "I'm engineering the best product for your profile. Stand by..."
        ),
        "analysis_complete": "<b>🎯 PLAN COMPLETED</b>",
        "investment": "Program Access Fee 💵",
        "no_product_found": "🚧 *Hold on.* I'm still refining a plan that fits your needs. Check back soon."
    },
    "AM": {
        "ask_gender": (
            "📍 *ምዕራፍ 1/5 — የሰውነት ተፈጥሮ* 🧬\n"
            "`▰▱▱▱▱` 20%\n\n"
            "በመጀመሪያ የማሰለጥነውን ሰው ማወቅ አለብኝ። ጾታዎን ይግለጹ፦"
        ),
        "ask_goal": (
            "📍 *ምዕራፍ 2/5 — ግብ* 🎯\n"
            "`▰▰▱▱▱` 40%\n\n"
            "ዋናው ግብዎ ምንድን ነው? ማሳካት የሚፈልጉትን ይምረጡ፦"
        ),
     "ask_level": (
    "📍 *ምዕራፍ 3 ከ 5 — የልምምድ ዳራ* ⚖️\n"
    "`▰▰▰▱▱` 60%\n\n"
    "እውነቱን እንነጋገር፤ አሁን ያለዎት ብቃት የትኛው ነው?\n\n"
    "• *ጀማሪ:* አዲስ ወይም አሁን የጀመሩ።\n"
    "• *መካከለኛ:* የሚሰሩ ግን ለውጥ የቆመባቸው።\n"
    "• *ዳሌ ላይ ያተኮረ:* ልዩ ትኩረት ለዳሌ እድገት የሚፈልጉ።\n"
    "• *የላቀ:* ከፍተኛ ውጤት የሚፈልጉ።"
),
        "ask_obstacle": (
            "📍 *ምዕራፍ 4/5 — እንቅፋቶች* 🚧\n"
            "`▰▰▰▰▱` 80%\n\n"
            "እስካሁን ትልቁ እንቅፋት የሆነብዎት ምንድን ነው? በታማኝነት አንዱን ይምረጡ፦"
        ),
        "ask_freq": (
            "📍 *ምዕራፍ 5/5 — የቁርጠኝነት ደረጃ* ⏳\n"
            "`▰▰▰▰▰` 100%\n\n"
            "ውጤት የሚመጣው ባለማቋረጥ ሲሰሩ ነው። በሳምንት ስንት ቀናትን መስራት ይችላሉ?"
        ),
        "analysis_start": (
            "📍 *ሲስተም የተቀናጀ* ⚙️\n\n"
            "ለሰውነትዎ የሚሆን ትክክለኛውን ስልት እያወጣሁ ነው..."
        ),
        "analysis_complete": "🎯 <b>ትክክለኛውን እቅድ አውጥቼሎታለው</b>",
        "investment": "የእቅዱ ዋጋ 💵",
        "no_product_found": "🚧 *ቆይ።* ለእርስዎ የሚሆን ትክክለኛ እቅድ ገና እያዘጋጀሁ ነው።"
    }
}

def get_text(lang: str, key: str) -> str:
    return STRINGS.get(lang, STRINGS.get("EN", {})).get(key, "")


def get_level_prompt(lang: str, gender: str = None) -> str:
    if lang == "EN":
        base = (
            "📍 <b>Step 3 of 5 — Experience Baseline</b> ⚖️\n"
            "`▰▰▰▱▱` 60%\n\n"
            "Be real with me. Where are you actually at?\n\n"
            "• <b>Beginner:</b> Just starting or restarting.\n"
            "• <b>Intermediate:</b> Consistent, but results have stalled.\n"
        )
        if gender != "MALE":
            base += "• <b>Glute Focused:</b> Specifically targeting lower body growth.\n"
        base += "• <b>Advanced:</b> Pushing for elite performance."
        return base
    else:  # Amharic
        base = (
            "📍 <b>ምዕራፍ 3 ከ 5 — የልምምድ ዳራ</b> ⚖️\n"
            "`▰▰▰▱▱` 60%\n\n"
            "እውነቱን እንነጋገር፤ አሁን ያለዎት ብቃት የትኛው ነው?\n\n"
            "• <b>ጀማሪ:</b> አዲስ ወይም አሁን የጀመሩ።\n"
            "• <b>መካከለኛ:</b> የሚሰሩ ግን ለውጥ የቆመባቸው።\n"
        )
        if gender != "MALE":
            base += "• <b>ዳሌ ተኮር:</b>ሙሉ የሰውነት እንቅስቅሴ።\n"
        base += "• <b>የላቀ:</b> ከፍተኛ ውጤት የሚፈልጉ።"
        return base
