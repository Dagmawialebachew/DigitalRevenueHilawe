"""Coach Hilawe Bilingual Content Glossary.

Authoritative source of truth for editorial Amharic and international English
translations across all foods, recipes, categories, meal slots, and portion measures.
"""
from __future__ import annotations

from typing import Any

# ==========================================
# 1. FOOD TRANSLATIONS (ID -> (EN, AM))
# ==========================================
FOOD_GLOSSARY: dict[str, tuple[str, str]] = {
    # Carbohydrates / Starches (C)
    "C001": ("Injera (Prepared)", "የተዘጋጀ እንጀራ"),
    "C002": ("Teff flour (Dry)", "የጤፍ ዱቄት (ጥሬ)"),
    "C003": ("White rice (Cooked)", "ነጭ ሩዝ (የበሰለ)"),
    "C004": ("Brown rice (Cooked)", "ቡናማ ሩዝ (የበሰለ)"),
    "C005": ("Pasta (Cooked)", "ፓስታ (የበሰለ)"),
    "C006": ("Whole-wheat pasta (Cooked)", "የሙሉ ስንዴ ፓስታ (የበሰለ)"),
    "C007": ("Oats (Dry)", "አጃ / ኦትስ (ጥሬ)"),
    "C008": ("Whole-wheat bread", "የሙሉ ስንዴ ዳቦ"),
    "C009": ("White bread", "ነጭ ዳቦ"),
    "C010": ("Potato (Boiled)", "የተቀቀለ ድንች"),
    "C011": ("Sweet potato (Cooked)", "ስኳር ድንች (የበሰለ)"),
    "C012": ("Corn (Boiled)", "የተቀቀለ በቆሎ"),
    "C013": ("Barley (Cooked)", "ገብስ / ቅንጬ (የበሰለ)"),
    "C014": ("Bulgur (Cooked)", "ቡልጉር (የበሰለ)"),
    "C015": ("Quinoa (Cooked)", "ኪኖዋ (የበሰለ)"),
    "C016": ("Whole-wheat tortilla", "የሙሉ ስንዴ ቶርቲላ"),
    "C017": ("Kocho (Prepared)", "የተዘጋጀ ቆጮ"),
    "C018": ("Kita flatbread", "የስንዴ ቂጣ"),
    "C019": ("Dabo bread", "የስንዴ ዳቦ"),
    "C020": ("Rice cake", "የሩዝ ኬክ (ክራከር)"),

    # Plant Proteins / Legumes (P)
    "P001": ("Red lentils (Cooked)", "ቀይ ምስር (የበሰለ)"),
    "P002": ("Yellow split peas (Cooked)", "የክክ ክክ (የበሰለ)"),
    "P003": ("Chickpeas (Cooked)", "ሽምብራ (የበሰለ)"),
    "P004": ("Fava beans (Cooked)", "ባቄላ (የበሰለ)"),
    "P005": ("Brown lentils (Cooked)", "ቡናማ ምስር (የበሰለ)"),
    "P006": ("Black beans (Cooked)", "ጥቁር ቦሎቄ (የበሰለ)"),
    "P007": ("Kidney beans (Cooked)", "ቀይ ቦሎቄ (የበሰለ)"),
    "P008": ("Shiro flour (Dry)", "የሽሮ ዱቄት (ጥሬ)"),
    "P009": ("Soy chunks / Textured soy (Dry)", "የሶያ ስጋ (ጥሬ)"),
    "P010": ("Firm tofu", "ቶፉ (የአኩሪ አተር አይብ)"),
    "P011": ("Tempeh", "ቴምፔ"),
    "P012": ("Edamame (Cooked)", "ኤዳማሜ / አረንጓዴ አኩሪ አተር"),
    "P013": ("Pea protein powder", "የአተር ፕሮቲን ዱቄት"),
    "P014": ("Soy protein isolate powder", "የሶያ ፕሮቲን ዱቄት"),
    "P015": ("Roasted chickpeas (Kolo)", "የተቆላ ሽምብራ (ቆሎ)"),
    "P016": ("Roasted barley (Kolo)", "የተቆላ ገብስ (ቆሎ)"),

    # Animal Proteins / Dairy / Fish (A)
    "A001": ("Chicken breast, skinless (Cooked)", "የዶሮ ደረት ስጋ (የበሰለ)"),
    "A002": ("Chicken thigh, skinless (Cooked)", "የዶሮ ጭን ስጋ (የበሰለ)"),
    "A003": ("Beef, lean steak (Cooked)", "የበሬ ስጋ (ቅባት የሌለው፣ የበሰለ)"),
    "A004": ("Ground beef, 90% lean (Cooked)", "የተፈጨ የበሬ ስጋ (የበሰለ)"),
    "A005": ("Goat meat (Cooked)", "የፍየል ስጋ (የበሰለ)"),
    "A006": ("Lamb, lean (Cooked)", "የበግ ስጋ (ቅባት የሌለው፣ የበሰለ)"),
    "A007": ("Tilapia fish (Cooked)", "የቲላፒያ ዓሣ (የበሰለ)"),
    "A008": ("Tuna, canned in water (Drained)", "ቱና በውሃ የታሸገ (የተጣራ)"),
    "A009": ("Salmon (Cooked)", "ሳልሞን ዓሣ (የበሰለ)"),
    "A010": ("Sardines, canned (Drained)", "ሰርዲን የታሸገ (የተጣራ)"),
    "A011": ("Egg, whole (Cooked)", "ሙሉ እንቁላል (የበሰለ)"),
    "A012": ("Egg whites (Cooked)", "የእንቁላል ነጭ ክፍል (የበሰለ)"),
    "A013": ("Greek yogurt, plain non-fat", "የግሪክ እርጎ (ቅባት አልባ)"),
    "A014": ("Yogurt, plain low-fat", "እርጎ (ዝቅተኛ ቅባት)"),
    "A015": ("Milk, low-fat", "ወተት (ዝቅተኛ ቅባት)"),
    "A016": ("Cottage cheese, low-fat", "ኮቴጅ ቺዝ (ዝቅተኛ ቅባት)"),
    "A017": ("Whey protein powder", "የዌይ ፕሮቲን ዱቄት"),
    "A018": ("Ayib (Fresh cottage cheese)", "የሀገር ባህል አይብ"),
    "A019": ("Turkey breast (Cooked)", "የቱርክ ደረት ስጋ (የበሰለ)"),
    "A020": ("White fish (Cooked)", "ነጭ ዓሣ (የበሰለ)"),

    # Vegetables (V)
    "V001": ("Onion (Raw)", "ቀይ ሽንኩርት (ጥሬ)"),
    "V002": ("Tomato (Raw)", "ቲማቲም (ጥሬ)"),
    "V003": ("Garlic (Raw)", "ነጭ ሽንኩርት (ጥሬ)"),
    "V004": ("Kale / Ethiopian Gomen (Cooked)", "ጎመን (የበሰለ)"),
    "V005": ("Collard greens (Cooked)", "የቆላ ጎመን (የበሰለ)"),
    "V006": ("Cabbage (Raw)", "ጥቅል ጎመን (ጥሬ)"),
    "V007": ("Carrot (Raw)", "ካሮት (ጥሬ)"),
    "V008": ("Green beans / Fosolia (Cooked)", "ፎሶሊያ (የበሰለ)"),
    "V009": ("Bell pepper (Raw)", "የፈረንጅ ቃሪያ / ቃሪያ (ጥሬ)"),
    "V010": ("Broccoli (Cooked)", "ብሮኮሊ (የበሰለ)"),
    "V011": ("Spinach (Cooked)", "ስፒናች (የበሰለ)"),
    "V012": ("Cucumber (Raw)", "ኪያር (ጥሬ)"),
    "V013": ("Lettuce (Raw)", "ሰላጣ (ጥሬ)"),
    "V014": ("Zucchini (Cooked)", "ዙኪኒ (የበሰለ)"),
    "V015": ("Mushrooms (Cooked)", "እንጉዳይ (የበሰለ)"),
    "V016": ("Beetroot (Cooked)", "ቀይ ስር (የበሰለ)"),
    "V017": ("Cauliflower (Cooked)", "አበባ ጎመን (የበሰለ)"),
    "V018": ("Eggplant (Cooked)", "ደበርጃን / የእንቁላል ተክል (የበሰለ)"),
    "V019": ("Okra (Cooked)", "ባሚያ (የበሰለ)"),
    "V020": ("Avocado", "አቮካዶ"),

    # Fruits (F)
    "F001": ("Banana", "ሙዝ"),
    "F002": ("Apple", "ፖም / አፕል"),
    "F003": ("Orange", "ብርቱካን"),
    "F004": ("Mango", "ማንጎ"),
    "F005": ("Papaya", "ፓፓያ"),
    "F006": ("Pineapple", "አናናስ"),
    "F007": ("Guava", "ዘይቱን / ጓቫ"),
    "F008": ("Strawberries", "ስትሮቤሪ"),
    "F009": ("Blueberries", "ብሉቤሪ"),
    "F010": ("Grapes", "ወይን"),
    "F011": ("Pear", "ፔር"),
    "F012": ("Dates (Dried)", "ቴምር (የደረቀ)"),
    "F013": ("Watermelon", "ሀብሀብ"),
    "F014": ("Peach", "ኮክ"),

    # Fats / Oils / Nuts / Seeds (T)
    "T001": ("Olive oil", "የወይራ ዘይት"),
    "T002": ("Sunflower oil", "የሱፍ ዘይት"),
    "T003": ("Peanuts (Roasted)", "የተቆላ ለውዝ"),
    "T004": ("Peanut butter", "የለውዝ ቅቤ"),
    "T005": ("Almonds", "አልሞንድ"),
    "T006": ("Walnuts", "ዋልነት"),
    "T007": ("Sesame seeds", "ሰሊጥ"),
    "T008": ("Sunflower seeds", "የሱፍ ፍሬ"),
    "T009": ("Chia seeds", "ቺያ ፍሬ"),
    "T010": ("Flaxseed (Ground)", "የተፈጨ ተልባ"),
    "T011": ("Butter", "ቅቤ"),
    "T012": ("Niter kibbeh (Spiced butter)", "ንጥር ቅቤ"),

    # Condiments / Spices / Beverages (M)
    "M001": ("Tomato paste", "የቲማቲም ድልህ (ሳልሳ)"),
    "M002": ("Lemon juice", "የሎሚ ጭማቂ"),
    "M003": ("Berbere spice blend", "የወጥ በርበሬ"),
    "M004": ("Sugar", "ስኳር"),
    "M005": ("Honey", "ማር"),
    "M006": ("Coffee, brewed (Unsweetened)", "የተፈላ ቡና (ያለ ስኳር)"),
    "M007": ("Tea, brewed (Unsweetened)", "ሻይ (ያለ ስኳር)"),
    "M008": ("Salt", "ጨው"),
    "M009": ("Unsweetened almond milk", "የአልሞንድ ወተት (ያለ ስኳር)"),
    "M010": ("Water", "ውሃ"),
}

# ==========================================
# 2. RECIPE TRANSLATIONS (ID -> (EN, AM))
# ==========================================
RECIPE_GLOSSARY: dict[str, tuple[str, str]] = {
    "R001": ("Coach Hilawe Shiro Wot", "የአሰልጣኝ ህላዌ ሽሮ ወጥ"),
    "R002": ("Coach Hilawe Misir Wot", "የአሰልጣኝ ህላዌ ምስር ወጥ"),
    "R003": ("Coach Hilawe Kik Alicha", "የአሰልጣኝ ህላዌ ክክ አልጫ"),
    "R004": ("Coach Hilawe Atkilt Wot", "የአሰልጣኝ ህላዌ አትክልት ወጥ"),
    "R005": ("Coach Hilawe Gomen", "የአሰልጣኝ ህላዌ የጎመን ወጥ"),
    "R006": ("Coach Hilawe Fosolia", "የአሰልጣኝ ህላዌ ፎሶሊያ በአትክልት"),
    "R007": ("Coach Hilawe Dinich Wot", "የአሰልጣኝ ህላዌ ድንች ወጥ"),
    "R008": ("Coach Hilawe Fasting Firfir", "የአሰልጣኝ ህላዌ የጾም ፍርፍር"),
    "R009": ("Coach Hilawe Fasting Ful", "የአሰልጣኝ ህላዌ የጾም ፉል"),
    "R010": ("Coach Hilawe Chickpea Salad", "የአሰልጣኝ ህላዌ የሽምብራ ሰላጣ"),
    "R011": ("Coach Hilawe Lentil Rice Bowl", "የአሰልጣኝ ህላዌ የምስር እና ሩዝ ቦውል"),
    "R012": ("Coach Hilawe Soy Tibs", "የአሰልጣኝ ህላዌ የሶያ ስጋ ጥብስ"),
    "R013": ("Coach Hilawe Tofu Tibs", "የአሰልጣኝ ህላዌ የቶፉ ጥብስ"),
    "R014": ("Coach Hilawe Fish Tibs", "የአሰልጣኝ ህላዌ የዓሣ ጥብስ"),
    "R015": ("Coach Hilawe Grilled Tilapia", "የአሰልጣኝ ህላዌ የተጠበሰ ቲላፒያ ዓሣ"),
    "R016": ("Coach Hilawe Doro Wot", "የአሰልጣኝ ህላዌ የዶሮ ወጥ"),
    "R017": ("Coach Hilawe Siga Wot", "የአሰልጣኝ ህላዌ የበሬ ስጋ ወጥ"),
    "R018": ("Coach Hilawe Lean Beef Tibs", "የአሰልጣኝ ህላዌ የበሬ ስጋ ጥብስ"),
    "R019": ("Coach Hilawe Chicken Tibs", "የአሰልጣኝ ህላዌ የዶሮ ስጋ ጥብስ"),
    "R020": ("Coach Hilawe Minchet Abish", "የአሰልጣኝ ህላዌ ምንቸት አብሽ"),
    "R021": ("Coach Hilawe Egg Firfir", "የአሰልጣኝ ህላዌ የእንቁላል ፍርፍር"),
    "R022": ("Coach Hilawe Cooked Lean Kitfo", "የአሰልጣኝ ህላዌ የበሰለ የክትፎ ስጋ"),
    "R023": ("Coach Hilawe Beef Alicha", "የአሰልጣኝ ህላዌ የበሬ ስጋ አልጫ"),
    "R024": ("Coach Hilawe Ayib Gomen Bowl", "የአሰልጣኝ ህላዌ የአይብ እና ጎመን ቦውል"),
    "R025": ("Coach Hilawe Yogurt Fruit Oat Bowl", "የአሰልጣኝ ህላዌ የእርጎ፣ ፍራፍሬ እና አጃ ቦውል"),
    "R026": ("Coach Hilawe Chicken Rice Bowl", "የአሰልጣኝ ህላዌ የዶሮ እና ሩዝ ቦውል"),
    "R027": ("Coach Hilawe Tuna Pasta", "የአሰልጣኝ ህላዌ የቱና ፓስታ"),
    "R028": ("Coach Hilawe Egg Avocado Toast", "የአሰልጣኝ ህላዌ የእንቁላል እና አቮካዶ ቶስት"),
}

# ==========================================
# 3. CATEGORY TRANSLATIONS (Key -> (EN, AM))
# ==========================================
CATEGORY_GLOSSARY: dict[str, tuple[str, str]] = {
    "Added fat": ("Added fat & oils", "የተጨመረ ቅባት እና ዘይት"),
    "Traditional added fat": ("Traditional butter & fats", "የሀገር ባህል ንጥር ቅቤ"),
    "Added sugar": ("Natural sweeteners & sugar", "ማጣፈጫ እና ስኳር"),
    "Animal protein": ("Animal protein", "የእንስሳት ፕሮቲን"),
    "Lean animal protein": ("Lean animal protein", "ቅባት አልባ የእንስሳት ፕሮቲን"),
    "Beverage": ("Beverages & hydration", "መጠጦች"),
    "Plant beverage": ("Plant-based milk", "የዕፅዋት ወተት"),
    "Condiment": ("Condiments & sauces", "ማጣፈጫዎች እና ድልህ"),
    "Dairy": ("Dairy products", "የወተት ተዋጽኦ"),
    "Dairy protein": ("Dairy protein", "የወተት ፕሮቲን"),
    "Traditional dairy protein": ("Traditional dairy cheese", "የሀገር ባህል አይብ"),
    "Dairy supplement": ("Dairy protein supplement", "የወተት ፕሮቲን ሰፕሊመንት"),
    "Plant supplement": ("Plant protein supplement", "የዕፅዋት ፕሮቲን ሰፕሊመንት"),
    "Dark green vegetable": ("Dark green vegetables", "አረንጓዴ ቅጠላማ አትክልቶች"),
    "Vegetable": ("Vegetables", "አትክልቶች"),
    "Vegetable / seasoning": ("Aromatics & seasonings", "ቅመማ ቅመም እና ማጣፈጫ"),
    "Egg protein": ("Eggs", "እንቁላል"),
    "Lean egg protein": ("Egg whites", "የእንቁላል ነጭ ክፍል"),
    "Fish protein": ("Fish & seafood", "ዓሣ እና የባህር ምግቦች"),
    "Fruit": ("Fresh fruits", "ትኩስ ፍራፍሬዎች"),
    "Fruit / dried": ("Dried fruits", "የደረቁ ፍራፍሬዎች"),
    "Fruit / fat": ("Healthy fat fruits", "ጠቃሚ ቅባት ያላቸው ፍራፍሬዎች"),
    "Grain / starch": ("Grains & starches", "እህል እና ስታርች"),
    "Traditional starch": ("Traditional Injera & starches", "የሀገር ባህል እንጀራ እና እህሎች"),
    "Tuber / starch": ("Root vegetables & tubers", "ስረ-መሬት አትክልቶች (ድንች)"),
    "Legume / plant protein": ("Legumes & plant protein", "ጥራጥሬ እና የዕፅዋት ፕሮቲን"),
    "Legume / vegetable": ("Legume vegetables", "ጥራጥሬ አትክልቶች"),
    "Legume flour": ("Legume flours (Shiro)", "የጥራጥሬ ዱቄት (ሽሮ)"),
    "Plant protein": ("Plant protein & soy", "የዕፅዋት ፕሮቲን እና አኩሪ አተር"),
    "Plant protein snack": ("Roasted legume snacks (Kolo)", "የተቆሉ የጥራጥሬ መክሰሶች (ቆሎ)"),
    "Nuts / fat": ("Nuts & nut butters", "ለውዝ እና የለውዝ ቅቤ"),
    "Seeds / fat": ("Seeds & seed oils", "ጠቃሚ ዘሮች (ሰሊጥ፣ ተልባ)"),
    "Seasoning": ("Seasonings & salt", "ቅመማ ቅመም እና ጨው"),
    "Spice": ("Spices & Berbere", "ቅመሞች እና በርበሬ"),
}

# ==========================================
# 4. RESOLUTION HELPERS
# ==========================================
def get_food_name(food_id: str, default_name: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    pair = FOOD_GLOSSARY.get(food_id)
    if pair:
        return pair[1] if lang == "AM" else pair[0]
    return default_name


def get_recipe_name(recipe_id: str, default_name: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    pair = RECIPE_GLOSSARY.get(recipe_id)
    if pair:
        return pair[1] if lang == "AM" else pair[0]
    return default_name


def get_category_name(category: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    norm = str(category or "").strip()
    pair = CATEGORY_GLOSSARY.get(norm)
    if pair:
        return pair[1] if lang == "AM" else pair[0]
    return norm


def get_slot_name(slot: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    slots_am = {
        "breakfast": "ቁርስ",
        "lunch": "ምሳ",
        "dinner": "እራት",
        "snack": "መክሰስ",
        "snack 1": "መክሰስ 1",
        "snack 2": "መክሰስ 2",
    }
    slots_en = {
        "breakfast": "Breakfast",
        "lunch": "Lunch",
        "dinner": "Dinner",
        "snack": "Snack",
        "snack 1": "Snack 1",
        "snack 2": "Snack 2",
    }
    key = slot.strip().lower()
    if lang == "AM":
        return slots_am.get(key, slot)
    return slots_en.get(key, slot)
