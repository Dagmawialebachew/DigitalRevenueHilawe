import sys
sys.stdout.reconfigure(encoding='utf-8')

def render_sample(is_female: bool, name: str, cur_wt: float, target_wt: float, kcal: int, protein: int, 
                  orig_price: int, discount: int, cuisine: str):
    discounted = orig_price - discount
    pct = round((discount / orig_price) * 100)
    
    if is_female:
        pronoun_1 = "የሞላሽውን"
        pronoun_2 = "ያለሽ"
        pronoun_3 = "ግብሽ"
        pronoun_4 = "ሜታቦሊዝምሽን"
        pronoun_5 = "የዕለት የካሎሪ ፍላጎትሽን"
        pronoun_6 = "የፕሮቲን መጠንሽን"
        pronoun_7 = "እቅድሽን"
        pronoun_8 = "ክፍያሽን በዚህ 2 ሰዓት ውስጥ የምትፈጽሚ ከሆነ"
        pronoun_9 = "አበረክትልሻለሁ"
        pronoun_10 = "የቀረችውን ክፍያ በቴሌብር ወይም በባንክ ፈጽመሽ ደረሰኙን እዚህ ላኪልኝ፤ እቅድሽን ወዲያውኑ ልኬልሽ አብረን እንጀምራለን"
        pronoun_11 = "የገባልሽን"
        pronoun_12 = "ኮፒ አድርገሽ እዚህ ላኪልኝ"
        pronoun_13 = "ካለሽ"
    else:
        pronoun_1 = "የሞላኸውን"
        pronoun_2 = "ያለህ"
        pronoun_3 = "ግብህ"
        pronoun_4 = "ሜታቦሊዝምህን"
        pronoun_5 = "የዕለት የካሎሪ ፍላጎትህን"
        pronoun_6 = "የፕሮቲን መጠንህን"
        pronoun_7 = "እቅድህን"
        pronoun_8 = "ክፍያህን በዚህ 2 ሰዓት ውስጥ የምትፈጽም ከሆነ"
        pronoun_9 = "አበረክትልሃለሁ"
        pronoun_10 = "የቀረችውን ክፍያ በቴሌብር ወይም በባንክ ፈጽመህ ደረሰኙን እዚህ ላክልኝ፤ እቅድህን ወዲያውኑ ልኬልህ አብረን እንጀምራለን"
        pronoun_11 = "የገባልህን"
        pronoun_12 = "ኮፒ አድርገህ እዚህ ላክልኝ"
        pronoun_13 = "ካለህ"
        
    cuisine_map = {
        "ETHIOPIAN": "ሙሉ በሙሉ በሀገራችን ምግቦች የተበጀውን",
        "MIXED": "በሀገራችንና በቀላል ዘመናዊ ምግቦች የተዋቀረውን",
    }
    cuisine_text = cuisine_map.get(cuisine, "በቀላሉ በሚገኙ ተመጣጣኝ ምግቦች የተዘጋጀውን")

    text = f"""🥗 <b>ሰላም {name}፣ አሰልጣኝ ህላዌ ነኝ።</b>
━━━━━━━━━━━━━━━━━━

በሲስተሜ {pronoun_1} የምግብ ፍላጎትና የሰውነት መረጃ በጥንቃቄ ገምግሜዋለሁ።

አሁን {pronoun_2} ክብደት <b>{cur_wt} ኪ.ግ</b> ሲሆን፣ {pronoun_3} ደግሞ ወደ <b>{target_wt} ኪ.ግ</b> የሰውነት ለውጥ ማምጣት እንደሆነ አይቻለሁ።

📊 {pronoun_4} በጥናት አስልቼ {pronoun_5} በ <b>{kcal:,} kcal</b> እና {pronoun_6} በ <b>{protein}g</b> መጥኜ {cuisine_text} {pronoun_7} ሰርቼ ጨርሻለሁ።

⚠️ <b>አስቸኳይ ማሳሰቢያ፦</b> እያንዳንዱን እቅድ በግል ስለምከታተል አሁን ላይ ከ 5 ሰዎች በላይ ማስተናገድ አልችልም። {pronoun_8} የ {discount:,} ብር ስጦታ {pronoun_9}።

🎁 <b>የ 2 ሰዓት የ{discount:,} ብር ልዩ ስጦታ፦</b>
├ መደበኛ ዋጋ፦ <s>{orig_price:,} ብር</s>
└ 🔥 <b>ለ{name} የተደረገ ዋጋ፦ {discounted:,} ብር ብቻ! ({pct}% ቅናሽ)</b>

{pronoun_10}፦

🏦 <b>የክፍያ አማራጮች (ለመቅዳት ቁጥሩን ይንኩት)፦</b>
• <b>የኢትዮጵያ ንግድ ባንክ (CBE)፦</b>
<code>1000599533641</code>
👤 <i>Hilawe Semma</i>

• <b>አቢሲኒያ ባንክ (BOA)፦</b>
<code>53299555</code>
👤 <i>Hilawe Semma</i>

• <b>ቴሌብር (Telebirr)፦</b>
<code>0953462846</code>
👤 <i>Hilawe Semma</i>

📲 <b>ደረሰኙን በፎቶ ወይም {pronoun_11} የባንክ/ቴሌብር SMS Message {pronoun_12}።</b>

ማንኛውም ጥያቄ {pronoun_13} በ @CoachHilaweSupportBot በኩል አናግረኝ።"""

    return text

print("=== MALE SAMPLE (Adu Lala - 30d Follow-up) ===")
print(render_sample(False, "Adu", 53.0, 67.0, 2850, 124, 8000, 1400, "ETHIOPIAN"))
print("\n" + "="*50 + "\n")
print("=== FEMALE SAMPLE (Selwa - 7d Plan) ===")
print(render_sample(True, "Selwa", 75.0, 65.0, 2075, 135, 3000, 800, "ETHIOPIAN"))
