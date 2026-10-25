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
    "C001": ("Injera", "እንጀራ"),
    "C002": ("Teff flour", "የጤፍ ዱቄት"),
    "C003": ("White rice (Cooked)", "ነጭ ሩዝ (የበሰለ)"),
    "C004": ("Brown rice (Cooked)", "ቡናማ ሩዝ (የበሰለ)"),
    "C005": ("Pasta (Cooked)", "ፓስታ (የበሰለ)"),
    "C006": ("Whole-wheat pasta (Cooked)", "የሙሉ ስንዴ ፓስታ (የበሰለ)"),
    "C007": ("Oats (Dry)", "አጃ / ኦትስ (ጥሬ)"),
    "C008": ("Whole-wheat bread", "የሙሉ ስንዴ ዳቦ"),
    "C009": ("White bread", "ነጭ ዳቦ"),
    "C010": ("Boiled potato", "የተቀቀለ ድንች"),
    "C011": ("Cooked sweet potato", "ስኳር ድንች"),
    "C012": ("Corn (Boiled)", "የተቀቀለ በቆሎ"),
    "C013": ("Cooked barley / Kinche", "ቅንጬ / ገብስ"),
    "C014": ("Bulgur (Cooked)", "ቡልጉር (የበሰለ)"),
    "C015": ("Quinoa (Cooked)", "ኪኖዋ (የበሰለ)"),
    "C016": ("Whole-wheat tortilla", "የሙሉ ስንዴ ቶርቲላ"),
    "C017": ("Kocho", "ቆጮ"),
    "C018": ("Kita flatbread", "የስንዴ ቂጣ"),
    "C019": ("Dabo bread", "የስንዴ ዳቦ"),
    "C020": ("Rice cakes", "የሩዝ ኬክ (ክራከር)"),

    # Plant Proteins / Legumes (P)
    "P001": ("Cooked lentils", "ምስር"),
    "P002": ("Cooked chickpeas", "ሽምብራ"),
    "P003": ("Black beans (Cooked)", "ጥቁር ቦሎቄ (የበሰለ)"),
    "P004": ("Kidney beans (Cooked)", "ቀይ ቦሎቄ (የበሰለ)"),
    "P005": ("White beans (Cooked)", "ነጭ ቦሎቄ (የበሰለ)"),
    "P006": ("Cooked split peas", "ክክ"),
    "P007": ("Cooked ful / fava beans", "ፉል (የበሰለ ባቄላ)"),
    "P008": ("Green peas (Cooked)", "አተር (የበሰለ)"),
    "P009": ("Dry soy chunks", "የሶያ ስጋ (ጥሬ)"),
    "P010": ("Firm tofu", "ቶፉ (የአኩሪ አተር አይብ)"),
    "P011": ("Tempeh", "ቴምፔ"),
    "P012": ("Shiro flour", "የሽሮ ዱቄት"),
    "P013": ("Roasted chickpeas (Kolo)", "የተቆላ ሽምብራ (ቆሎ)"),
    "P014": ("Soy milk (unsweetened)", "የአኩሪ አተር ወተት"),
    "P015": ("Plant protein powder (Pea/Soy)", "የዕፅዋት ፕሮቲን ዱቄት (አተር/ሶያ)"),

    # Animal Proteins / Dairy / Fish (A)
    "A001": ("Cooked chicken breast", "የዶሮ ደረት ስጋ"),
    "A002": ("Cooked chicken thigh", "የዶሮ ጭን ስጋ"),
    "A003": ("Lean beef", "የበሬ ቀይ ስጋ"),
    "A004": ("Lean ground beef", "የተፈጨ የበሬ ስጋ"),
    "A005": ("Cooked goat meat", "የፍየል ስጋ"),
    "A006": ("Lean lamb", "የበግ ስጋ"),
    "A007": ("Cooked tilapia", "የቲላፒያ ዓሣ"),
    "A008": ("Canned tuna in water", "የታሸገ ቱና (በውሃ የተዘጋጀ)"),
    "A009": ("Salmon (Cooked)", "ሳልሞን ዓሣ (የበሰለ)"),
    "A010": ("Sardines, canned (Drained)", "ሰርዲን የታሸገ (የተጣራ)"),
    "A011": ("Boiled whole egg", "የተቀቀለ እንቁላል"),
    "A012": ("Boiled egg white", "የተቀቀለ የእንቁላል ነጭ"),
    "A013": ("Greek yogurt (non-fat)", "የግሪክ እርጎ (ቅባት አልባ)"),
    "A014": ("Low-fat yogurt", "እርጎ (ዝቅተኛ ቅባት)"),
    "A015": ("Milk, low-fat", "ወተት (ዝቅተኛ ቅባት)"),
    "A016": ("Cottage cheese, low-fat", "ኮቴጅ ቺዝ (ዝቅተኛ ቅባት)"),
    "A017": ("Whey protein powder", "የዌይ ፕሮቲን ዱቄት"),
    "A018": ("Ayib (Ethiopian cheese)", "የአበሻ አይብ"),
    "A019": ("Turkey breast (Cooked)", "የቱርክ ደረት ስጋ (የበሰለ)"),
    "A020": ("White fish (Cooked)", "ነጭ ዓሣ (የበሰለ)"),

    # Vegetables (V)
    "V001": ("Onion (Raw)", "ቀይ ሽንኩርት (ጥሬ)"),
    "V002": ("Tomato (Raw)", "ቲማቲም (ጥሬ)"),
    "V003": ("Garlic (Raw)", "ነጭ ሽንኩርት (ጥሬ)"),
    "V004": ("Ethiopian kale (Gomen)", "የሀበሻ ጎመን"),
    "V005": ("Collard greens", "የቆላ ጎመን"),
    "V006": ("Cabbage", "ጥቅል ጎመን"),
    "V007": ("Carrot (Raw)", "ካሮት (ጥሬ)"),
    "V008": ("Green beans (Fosolia)", "ፎሶሊያ"),
    "V009": ("Green pepper", "ቃሪያ / የፈረንጅ ቃሪያ"),
    "V010": ("Cooked broccoli", "ብሮኮሊ"),
    "V011": ("Spinach (Cooked)", "ስፒናች (የበሰለ)"),
    "V012": ("Cucumber", "ኪያር"),
    "V013": ("Lettuce / Salad", "ሰላጣ"),
    "V014": ("Zucchini (Cooked)", "ዙኪኒ (የበሰለ)"),
    "V015": ("Mushrooms (Cooked)", "እንጉዳይ (የበሰለ)"),
    "V016": ("Beetroot (Cooked)", "ቀይ ስር (የበሰለ)"),
    "V017": ("Cauliflower (Cooked)", "አበባ ጎመን (የበሰለ)"),
    "V018": ("Eggplant", "ደበርጃን"),
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
    "T003": ("Roasted peanuts", "የተቆላ ለውዝ"),
    "T004": ("Peanut butter", "የለውዝ ቅቤ"),
    "T005": ("Almonds", "አልሞንድ"),
    "T006": ("Walnuts", "ዋልነት"),
    "T007": ("Sesame seeds", "ሰሊጥ"),
    "T008": ("Sunflower seeds", "የሱፍ ፍሬ"),
    "T009": ("Chia seeds", "ቺያ ፍሬ"),
    "T010": ("Flaxseed (Ground)", "የተፈጨ ተልባ"),
    "T011": ("Butter", "ቅቤ"),
    "T012": ("Spiced butter (Niter kibbeh)", "ንጥር ቅቤ"),

    # Condiments / Spices / Beverages (M)
    "M001": ("Tomato paste", "የቲማቲም ድልህ (ሳልሳ)"),
    "M002": ("Lemon juice", "የሎሚ ጭማቂ"),
    "M003": ("Berbere", "የወጥ በርበሬ"),
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
    "R001": ("Shiro Wot", "ሽሮ ወጥ"),
    "R002": ("Misir Wot", "ምስር ወጥ"),
    "R003": ("Kik Alicha", "ክክ አልጫ ወጥ"),
    "R004": ("Atkilt Wot", "የአትክልት ወጥ"),
    "R005": ("Gomen Wot", "የጎመን ወጥ"),
    "R006": ("Fosolia Stew", "ፎሶሊያ በአትክልት"),
    "R007": ("Dinich Wot", "የድንች ወጥ"),
    "R008": ("Fasting Firfir", "የጾም ፍርፍር"),
    "R009": ("Fasting Ful Bowl", "የጾም ፉል"),
    "R010": ("Chickpea Salad", "የሽምብራ ሰላጣ"),
    "R011": ("Lentil Rice Bowl", "ምስር በሩዝ"),
    "R012": ("Soy Tibs", "የሶያ ስጋ ጥብስ"),
    "R013": ("Tofu Tibs", "የቶፉ ጥብስ"),
    "R014": ("Fish Tibs", "የዓሣ ጥብስ"),
    "R015": ("Grilled Tilapia Fillet", "የተጠበሰ የቲላፒያ ዓሣ"),
    "R016": ("Doro Wot", "የዶሮ ወጥ"),
    "R017": ("Siga Wot", "የበሬ ስጋ ወጥ"),
    "R018": ("Beef Tibs", "የበሬ ስጋ ጥብስ"),
    "R019": ("Chicken Tibs", "የዶሮ ስጋ ጥብስ"),
    "R020": ("Minchet Abish", "ምንቸት አብሽ"),
    "R021": ("Egg Firfir", "የእንቁላል ፍርፍር"),
    "R022": ("Lean Kitfo (Cooked)", "የበሰለ ክትፎ"),
    "R023": ("Beef Key Wot", "ቀይ ወጥ"),
    "R024": ("Ayib Gomen Bowl", "አይብ በጎመን"),
    "R025": ("Yogurt Oat Bowl", "እርጎ በአጃና ፍራፍሬ"),
    "R026": ("Chicken Rice Bowl", "የዶሮ ስጋ ከሩዝ ጋር"),
    "R027": ("Tuna Pasta", "ቱና ከፓስታ ጋር"),
    "R028": ("Egg Avocado Toast", "እንቁላልና አቮካዶ በዳቦ"),
}

# ==========================================
# 3. CATEGORY TRANSLATIONS (Key -> (EN, AM))
# ==========================================
CATEGORY_GLOSSARY: dict[str, tuple[str, str]] = {
    "Added fat": ("Added fat & oils", "ዘይት እና ቅባቶች"),
    "Traditional added fat": ("Traditional butter & fats", "የሀበሻ ንጥር ቅቤ"),
    "Added sugar": ("Natural sweeteners & sugar", "ማጣፈጫ እና ስኳር"),
    "Animal protein": ("Animal protein", "የእንስሳት ውጤቶች"),
    "Lean animal protein": ("Lean animal protein", "ስጋ እና የዶሮ ውጤቶች"),
    "Beverage": ("Beverages & hydration", "መጠጦች"),
    "Plant beverage": ("Plant-based milk", "የዕፅዋት ወተት"),
    "Condiment": ("Condiments & sauces", "ማጣፈጫዎች እና ድልህ"),
    "Dairy": ("Dairy products", "የወተት ተዋጽኦ"),
    "Dairy protein": ("Dairy protein", "የወተት ውጤቶች"),
    "Traditional dairy protein": ("Traditional dairy cheese", "የአበሻ አይብ"),
    "Dairy supplement": ("Dairy protein supplement", "የወተት ሰፕሊመንት"),
    "Plant supplement": ("Plant protein supplement", "የዕፅዋት ሰፕሊመንት"),
    "Dark green vegetable": ("Dark green vegetables", "አረንጓዴ ቅጠላማ አትክልቶች"),
    "Vegetable": ("Vegetables", "አትክልቶች"),
    "Vegetable / seasoning": ("Aromatics & seasonings", "ቅመማ ቅመም እና ማጣፈጫ"),
    "Egg protein": ("Eggs", "እንቁላል"),
    "Lean egg protein": ("Egg whites", "የእንቁላል ነጭ ክፍል"),
    "Fish protein": ("Fish & seafood", "ዓሣ እና የባህር ምግቦች"),
    "Fruit": ("Fresh fruits", "ትኩስ ፍራፍሬዎች"),
    "Fruit / dried": ("Dried fruits", "የደረቁ ፍራፍሬዎች"),
    "Fruit / fat": ("Healthy fat fruits", "ጠቃሚ ቅባት ያላቸው ፍራፍሬዎች"),
    "Grain / starch": ("Grains & starches", "እህሎች እና የሃይል ምንጮች"),
    "Traditional starch": ("Traditional Injera & starches", "እንጀራ እና እህሎች"),
    "Tuber / starch": ("Root vegetables & tubers", "ድንች እና ስራስር"),
    "Legume / plant protein": ("Legumes & plant protein", "ጥራጥሬ እና የዕፅዋት ውጤቶች"),
    "Legume / vegetable": ("Legume vegetables", "ጥራጥሬ አትክልቶች"),
    "Legume flour": ("Legume flours (Shiro)", "የሽሮ ዱቄት"),
    "Plant protein": ("Plant protein & soy", "የጾም ውጤቶች"),
    "Plant protein snack": ("Roasted legume snacks (Kolo)", "የተቆሉ የጥራጥሬ መክሰሶች (ቆሎ)"),
    "Nuts / fat": ("Nuts & nut butters", "ለውዝ እና የለውዝ ቅቤ"),
    "Seeds / fat": ("Seeds & seed oils", "ጠቃሚ ዘሮች (ሰሊጥ፣ ተልባ)"),
    "Seasoning": ("Seasonings & salt", "ቅመማ ቅመም እና ጨው"),
    "Spice": ("Spices & Berbere", "ቅመሞች እና በርበሬ"),
}

# ==========================================
# 4. TEMPLATE TRANSLATIONS (64 MEAL TEMPLATES)
# ==========================================
TEMPLATE_GLOSSARY: dict[str, tuple[str, str]] = {
    "MN-B01": ("Eggs, injera and tomato", "እንቁላል ከእንጀራ እና ቲማቲም ጋር"),
    "MN-B02": ("Yogurt fruit oat bowl", "እርጎ ከፍራፍሬ እና አጃ (ኦትስ) ጋር"),
    "MN-B03": ("Egg avocado toast", "የእንቁላል እና አቮካዶ ቶስት"),
    "MN-B04": ("Boiled eggs, bread and orange", "የተቀቀለ እንቁላል ከዳቦ እና ብርቱካን ጋር"),
    "MN-B05": ("Greek yogurt, banana and peanuts", "የግሪክ እርጎ፣ ሙዝ እና ለውዝ"),
    "MN-B06": ("Ayib, injera and papaya", "የአበሻ አይብ ከእንጀራ እና ፓፓያ ጋር"),
    "MN-B07": ("Egg firfir and cucumber", "የእንቁላል ፍርፍር ከኪያር ጋር"),
    "MN-S-SHAKE": ("High-calorie strength shake", "የጥንካሬ ሼክ / ፈጣን መክሰስ"),
    "MF-B01": ("Fasting ful with injera", "የጾም ፉል ከእንጀራ ጋር"),
    "MF-B02": ("Oats, soy milk, banana and peanut", "አጃ (ኦትስ)፣ የአኩሪ አተር ወተት፣ ሙዝ እና ለውዝ"),
    "MF-B03": ("Chickpea salad with injera", "የሽምብራ ሰላጣ ከእንጀራ ጋር"),
    "MF-B04": ("Fasting firfir with soy protein", "የጾም ፍርፍር ከሶያ ፕሮቲን ጋር"),
    "MF-B05": ("Lentil rice breakfast bowl", "የምስር ሩዝ ቁርስ ሳህን"),
    "MF-B06": ("Tofu, bread and tomato", "ቶፉ ከዳቦ እና ቲማቲም ጋር"),
    "MF-B07": ("Peanut banana oats", "አጃ (ኦትስ) በለውዝ እና ሙዝ"),
    "MN-L01": ("Chicken rice bowl", "የዶሮ ስጋ ከሩዝ ጋር"),
    "MN-L02": ("Beef tibs, injera and salad", "የበሬ ጥብስ ከእንጀራ እና ሰላጣ ጋር"),
    "MN-L03": ("Tuna pasta and tomato", "ቱና ከፓስታ እና ቲማቲም ጋር"),
    "MN-L04": ("Doro wot, injera and gomen", "የዶሮ ወጥ ከእንጀራ እና ጎመን ጋር"),
    "MN-L05": ("Siga wot, injera and fosolia", "የስጋ ወጥ ከእንጀራ እና ፎሶሊያ ጋር"),
    "MN-L06": ("Chicken tibs, potato and broccoli", "የዶሮ ጥብስ ከድንች እና ብሮኮሊ ጋር"),
    "MN-L07": ("Beef key wot and injera", "ቀይ ወጥ ከእንጀራ ጋር"),
    "MN-L08": ("Turkey quinoa vegetable bowl", "የቱርክ ደረት ስጋ ከኩዊኖአ እና አትክልት ጋር"),
    "MF-L01": ("Misir wot, injera and gomen", "የምስር ወጥ ከእንጀራ እና ጎመን ጋር"),
    "MF-L02": ("Shiro wot, injera and salad", "የሽሮ ወጥ ከእንጀራ እና ሰላጣ ጋር"),
    "MF-L03": ("Kik alicha, injera and atkilt", "የክክ አልጫ ከእንጀራ እና አትክልት ጋር"),
    "MF-L04": ("Soy tibs and brown rice", "የሶያ ጥብስ ከቡናማ ሩዝ ጋር"),
    "MF-L05": ("Tofu tibs and injera", "የቶፉ ጥብስ ከእንጀራ ጋር"),
    "MF-L06": ("Chickpea salad and sweet potato", "የሽምብራ ሰላጣ ከስኳር ድንች ጋር"),
    "MF-L07": ("Fish tibs and rice", "የዓሣ ጥብስ ከሩዝ ጋር"),
    "MF-L08": ("White bean rice vegetable bowl", "የነጭ ቦሎቄ ሩዝ እና አትክልት"),
    "MN-D01": ("Grilled tilapia, potato and vegetables", "የተጠበሰ የቲላፒያ ዓሣ ከድንች እና አትክልት ጋር"),
    "MN-D02": ("Minchet abish, injera and salad", "ምንቸት አብሽ ከእንጀራ እና ሰላጣ ጋር"),
    "MN-D03": ("Cooked lean kitfo, gomen and kocho", "የበሰለ ክትፎ ከጎመን እና ቆጮ ጋር"),
    "MN-D04": ("Egg firfir and salad", "የእንቁላል ፍርፍር ከሰላጣ ጋር"),
    "MN-D05": ("Ayib gomen bowl and injera", "የአይብ ጎመን ከእንጀራ ጋር"),
    "MN-D06": ("Chicken rice bowl and broccoli", "የዶሮ ስጋ ከሩዝ እና ብሮኮሊ ጋር"),
    "MN-D07": ("Tuna, brown rice and cucumber", "ቱና ከቡናማ ሩዝ እና ኪያር ጋር"),
    "MN-D08": ("Lean beef pasta and broccoli", "የተፈጨ የበሬ ስጋ ከፓስታ እና ብሮኮሊ ጋር"),
    "MN-D09": ("Chicken, sweet potato and green beans", "የዶሮ ስጋ ከስኳር ድንች እና ፎሶሊያ ጋር"),
    "MF-D01": ("Lentil rice bowl and broccoli", "የምስር ሩዝ እና ብሮኮሊ"),
    "MF-D02": ("Fasting ful, injera and tomato", "የጾም ፉል ከእንጀራ እና ቲማቲም ጋር"),
    "MF-D03": ("Dinich wot with soy chunks", "ድንች ወጥ ከሶያ ስጋ ጋር"),
    "MF-D04": ("Shiro, gomen and injera", "ሽሮ ወጥ ከጎመን እና እንጀራ ጋር"),
    "MF-D05": ("Grilled tilapia, potato and vegetables", "የተጠበሰ የቲላፒያ ዓሣ ከድንች እና አትክልት ጋር"),
    "MF-D06": ("Tofu tibs and brown rice", "የቶፉ ጥብስ ከቡናማ ሩዝ ጋር"),
    "MF-D07": ("Misir, atkilt and injera", "ምስር ወጥ ከአትክልት እና እንጀራ ጋር"),
    "MF-D08": ("Soy chunk pasta and vegetables", "የሶያ ስጋ ፓስታ ከአትክልት ጋር"),
    "MN-S01": ("Greek yogurt and apple", "የግሪክ እርጎ ከፖም (አፕል) ጋር"),
    "MN-S02": ("Whey and banana", "የዌይ ፕሮቲን ከሙዝ ጋር"),
    "MN-S03": ("Milk and peanuts", "ወተት ከለውዝ ጋር"),
    "MN-S04": ("Cottage cheese and pineapple", "ኮቴጅ ቺዝ ከአናናስ ጋር"),
    "MN-S05": ("Eggs and orange", "የተቀቀለ እንቁላል ከብርቱካን ጋር"),
    "MN-S06": ("Ayib and cucumber", "የአበሻ አይብ ከኪያር ጋር"),
    "MN-S07": ("Tuna and rice cakes", "ቱና ከሩዝ ኬክ (ክራከር) ጋር"),
    "MN-S08": ("Greek yogurt and berries", "የግሪክ እርጎ ከቤሪ ፍራፍሬ ጋር"),
    "MN-S09": ("Peanut butter, banana and rice cakes", "የለውዝ ቅቤ፣ ሙዝ እና የሩዝ ኬክ"),
    "MF-S01": ("Apple and peanuts", "ፖም (አፕል) ከለውዝ ጋር"),
    "MF-S02": ("Soy milk and banana", "የአኩሪ አተር ወተት ከሙዝ ጋር"),
    "MF-S03": ("Roasted chickpeas and orange", "የተቆላ ሽምብራ (ቆሎ) ከብርቱካን ጋር"),
    "MF-S04": ("Peanut butter and apple", "የለውዝ ቅቤ ከፖም (አፕል) ጋር"),
    "MF-S05": ("Dates and peanuts", "ቴምር ከለውዝ ጋር"),
    "MF-S06": ("Plant protein and banana", "የዕፅዋት ፕሮቲን ዱቄት ከሙዝ ጋር"),
    "MF-S07": ("Tofu and papaya bowl", "ቶፉ ከፓፓያ ጋር"),
    "MF-S08": ("Soy oat fruit shake", "የሶያ፣ አጃ እና ፍራፍሬ ሼክ"),
}

# ==========================================
# 5. RECIPE METHODS & SUMMARIES (AMHARIC)
# ==========================================
RECIPE_METHODS_AM: dict[str, str] = {
    "R001": "ሽንኩርቱን በዝግታ ያቁላሉ፤ የተለካውን ዘይት እና ቅመሞች ይጨምሩ፤ የሽሮውን ዱቄት ከውሃ ጋር በጥብጠው እየአማሰሉ ያፍሉት፤ እስኪወፍር ድረስ በዝቅተኛ እሳት ያብስሉ። የበሰለውን አጠቃላይ መጠን ይመዝኑ።",
    "R002": "ሽንኩርቱን በዘይት እና በርበሬ ያቁላሉ፤ ምስሩን እና ቲማቲሙን ጨምረው በደንብ ያብስሉ። የበሰለውን ሙሉ መጠን ይመዝኑ።",
    "R003": "ሽንኩርት እና ነጭ ሽንኩርቱን በዘይት ያቁላሉ፤ ከተቀቀለው ለስላሳ ክክ ጋር ይቀላቅሉ፤ በቅመሞች አጣፍጠው የበሰለውን መጠን ይመዝኑ።",
    "R004": "አትክልቶቹን በተወሰነ ዘይት እና አነስተኛ ውሃ እስኪለሰልሱ ድረስ ያብስሉ። ከመከፋፈሉ በፊት የበሰለውን አጠቃላይ ክብደት ይመዝኑ።",
    "R005": "ጎመኑን ከሽንኩርት እና ነጭ ሽንኩርት ጋር በተለካ ዘይት ያብስሉ። ውሃው ከተጣራ በኋላ የተመዘገበውን የመጨረሻ መጠን ይያዙ።",
    "R006": "ፎሶሊያ፣ ካሮት፣ ሽንኩርት እና ቲማቲሙን በተለካ ዘይት አብረው ያብስሉ፤ ተገቢውን እርጥበት ጠብቀው ሙሉውን መጠን ይመዝኑ።",
    "R007": "ሽንኩርት፣ ቲማቲም እና በርበሬውን በዘይት ያቁላሉ፤ ድንቹን እና ውሃ ጨምረው እስኪበስል ያቆዩ። የበሰለውን ድምር ይመዝኑ።",
    "R008": "የቲማቲም እና በርበሬ ኩስ ያዘጋጁ፤ ከመመገብዎ በፊት የተቆራረጠውን እንጀራ ጨምረው አዋህደው የበሰለውን መጠን ይመዝኑ።",
    "R009": "ፉሉን አሞቀው በትንሹ ያድቅቁ፤ የተከተፉ ትኩስ አትክልቶችን እና የተለካ ዘይት ይጨምሩ፤ በሎሚ ጭማቂ አጣፍጠው ይመዝኑ።",
    "R010": "የተጣራውን ሽምብራ ከተከተፉ አትክልቶች፣ የወይራ ዘይት እና ሎሚ ጋር ያዋህዱ። የተዘጋጀውን ሙሉ መጠን ይመዝኑ።",
    "R011": "የበሰለውን ምስር፣ ሩዝ እና አትክልቶችን በአንድ ሳህን ያዘጋጁ፤ የተለካውን ድሬሲንግ ጨምረው በወጥነት ይመዝኑ።",
    "R012": "የሶያ ስጋውን በውሃ አርጥበው ውሃውን ያጥፉ፤ ከአትክልቶች፣ ቅመሞች እና ከተለካ ዘይት ጋር ያጥብሱት፤ የመጨረሻውን የበሰለ ክብደት ይመዝኑ።",
    "R013": "ቶፉውን ውሃውን አጥርተው በዘይት በትንሹ ያቅሉት፤ አትክልት እና ቅመሞችን ጨምረው የበሰለውን መጠን ይመዝኑ።",
    "R014": "ዓሣውን በጥንቃቄ አብስለው ከአትክልቶች እና ከተለካ ዘይት ጋር በትንሹ ያገላብጡት፤ ሙሉውን መጠን ይመዝኑ። (የጾም ዓሣ ለሚፈቅዱ ብቻ)",
    "R015": "ዓሣውን በደንብ እስኪበስል ድረስ ይጥበሱት፤ የሚበላውን ትክክለኛ የበሰለ ክብደት መዝነው ይመገቡ።",
    "R016": "ሽንኩርቱን በዝግታ ያቁላሉ፤ የተለካ ዘይት እና በርበሬ ይጨምሩ፤ የዶሮውን ስጋ ጨምረው ያብስሉ፤ እንቁላሉን ጨምረው የበሰለውን ድምር ይመዝኑ።",
    "R017": "ሽንኩርት እና በርበሬውን በዘይት ያቁላሉ፤ ስጋውን ጨምረው እስኪለሰልስ ድረስ ያብስሉ፤ የበሰለውን ሙሉ መጠን ይመዝኑ።",
    "R018": "ስጋውን በደንብ ያብስሉ፤ አትክልቶችን እና የተለካውን ዘይት ጨምረው በፍጥነት ያገላብጡ፤ የበሰለውን መጠን ይመዝኑ።",
    "R019": "የዶሮውን ስጋ በደንብ ያብስሉ፤ አትክልት እና የተለካ ዘይት ጨምረው አዋህደው የበሰለውን መጠን ይመዝኑ።",
    "R020": "የተፈጨውን ስጋ ከሽንኩርት፣ ቅመማ ቅመም እና የተለካ ዘይት ጋር በደንብ ያብስሉ፤ የበሰለውን መጠን ይመዝኑ።",
    "R021": "ኩሱን አዘጋጅተው እንቁላሉን ይጥበሱ፤ ከመቅረቡ በፊት የተቆራረጠውን እንጀራ ቀላቅለው የበሰለውን መጠን ይመዝኑ።",
    "R022": "ለአጠቃላይ ጤና ተስማሚ እንዲሆን የተፈጨውን ስጋ በትንሹ ለብ ያድርጉት፤ ከተለካው ቅቤ እና ቅመም ጋር አዋህደው ይመዝኑ።",
    "R023": "ስጋውን እና አትክልቶቹን በተለካ ዘይት እና ማጣፈጫ በዝግታ ያብስሉ፤ የበሰለውን አጠቃላይ መጠን ይመዝኑ።",
    "R024": "የተለካውን አይብ ከተበሰለ ጎመን እና ድሬሲንግ ጋር ያዋህዱ፤ ሙሉውን ድምር ይመዝኑ።",
    "R025": "እርጎውን፣ አጃውን፣ ሙዙን እና ለውዙን ከመመገብዎ በፊት ወዲያውኑ በአንድ ላይ ያዋህዱ።",
    "R026": "የበሰሉትን ክፍሎች በአንድ ላይ ያዘጋጁ፤ የተለካውን የወይራ ዘይት እና ሎሚ ጨምረው ይመዝኑ።",
    "R027": "የተጣራውን ቱና፣ የበሰለውን ፓስታ እና ትኩስ አትክልቶችን ከተለካ ዘይት ጋር ይቀላቅሉ።",
    "R028": "እንቁላሉን ቀቅለው ወይም ጥብሰው በሙሉ ስንዴ ዳቦ ላይ ከተፈጨ አቮካዶ ጋር አዘጋጅተው ወዲያውኑ ይመገቡ።",
}

RECIPE_SUMMARIES_AM: dict[str, str] = {
    "R001": "የሽሮ ዱቄት 200 ግ፤ ቀይ ሽንኩርት 300 ግ፤ ቲማቲም 200 ግ፤ ነጭ ሽንኩርት 10 ግ፤ የሱፍ ዘይት 30 ግ፤ የወጥ በርበሬ 10 ግ፤ የቲማቲም ድልህ 50 ግ",
    "R002": "ምስር 800 ግ፤ ቀይ ሽንኩርት 250 ግ፤ ቲማቲም 180 ግ፤ ነጭ ሽንኩርት 10 ግ፤ የሱፍ ዘይት 25 ግ፤ የወጥ በርበሬ 12 ግ፤ የቲማቲም ድልህ 40 ግ",
    "R003": "የክክ ክክ 800 ግ፤ ቀይ ሽንኩርት 220 ግ፤ ነጭ ሽንኩርት 8 ግ፤ የሱፍ ዘይት 20 ግ፤ ካሮት 100 ግ፤ የሎሚ ጭማቂ 20 ግ",
    "R004": "የተቀቀለ ድንች 450 ግ፤ ጥቅል ጎመን 400 ግ፤ ካሮት 250 ግ፤ ቀይ ሽንኩርት 180 ግ፤ የሱፍ ዘይት 20 ግ፤ ነጭ ሽንኩርት 8 ግ",
    "R005": "የጎመን ቅጠል 700 ግ፤ ቀይ ሽንኩርት 150 ግ፤ ነጭ ሽንኩርት 8 ግ፤ የሱፍ ዘይት 20 ግ፤ የሎሚ ጭማቂ 20 ግ",
    "R006": "ፎሶሊያ 600 ግ፤ ካሮት 250 ግ፤ ቀይ ሽንኩርት 180 ግ፤ ቲማቲም 150 ግ፤ የሱፍ ዘይት 20 ግ",
    "R007": "የተቀቀለ ድንች 900 ግ፤ ቀይ ሽንኩርት 250 ግ፤ ቲማቲም 180 ግ፤ የሱፍ ዘይት 30 ግ፤ የወጥ በርበሬ 10 ግ፤ ነጭ ሽንኩርት 10 ግ",
    "R008": "እንጀራ 400 ግ፤ ቀይ ሽንኩርት 150 ግ፤ ቲማቲም 180 ግ፤ የሱፍ ዘይት 20 ግ፤ የወጥ በርበሬ 10 ግ፤ የቲማቲም ድልህ 40 ግ",
    "R009": "የበሰለ ባቄላ (ፉል) 800 ግ፤ ቲማቲም 150 ግ፤ ቀይ ሽንኩርት 100 ግ፤ የሱፍ ዘይት 15 ግ፤ የሎሚ ጭማቂ 25 ግ፤ ቃሪያ 40 ግ",
    "R010": "የበሰለ ሽምብራ 600 ግ፤ ቲማቲም 150 ግ፤ ኪያር 150 ግ፤ ቀይ ሽንኩርት 70 ግ፤ የወይራ ዘይት 20 ግ፤ የሎሚ ጭማቂ 30 ግ",
    "R011": "የበሰለ ምስር 600 ግ፤ የበሰለ ቡናማ ሩዝ 500 ግ፤ የበሰለ ብሮኮሊ 200 ግ፤ ቃሪያ 80 ግ፤ የወይራ ዘይት 15 ግ፤ የሎሚ ጭማቂ 30 ግ",
    "R012": "የሶያ ስጋ 200 ግ፤ ቀይ ሽንኩርት 180 ግ፤ ቃሪያ 180 ግ፤ ቲማቲም 150 ግ፤ የሱፍ ዘይት 20 ግ፤ ነጭ ሽንኩርት 10 ግ፤ የወጥ በርበሬ 8 ግ",
    "R013": "ቶፉ 800 ግ፤ ቀይ ሽንኩርት 180 ግ፤ ቃሪያ 180 ግ፤ ቲማቲም 120 ግ፤ የሱፍ ዘይት 15 ግ፤ ነጭ ሽንኩርት 8 ግ",
    "R014": "የበሰለ ቲላፒያ ዓሣ 800 ግ፤ ቀይ ሽንኩርት 160 ግ፤ ቃሪያ 120 ግ፤ ቲማቲም 100 ግ፤ የሱፍ ዘይት 20 ግ፤ የሎሚ ጭማቂ 30 ግ",
    "R015": "የበሰለ ቲላፒያ ዓሣ 800 ግ፤ የወይራ ዘይት 10 ግ፤ የሎሚ ጭማቂ 30 ግ",
    "R016": "የዶሮ ጭን ስጋ 800 ግ፤ ሙሉ እንቁላል 200 ግ፤ ቀይ ሽንኩርት 600 ግ፤ ቲማቲም 120 ግ፤ የሱፍ ዘይት 40 ግ፤ የወጥ በርበሬ 25 ግ፤ ነጭ ሽንኩርት 12 ግ",
    "R017": "የበሬ ስጋ 800 ግ፤ ቀይ ሽንኩርት 550 ግ፤ ቲማቲም 180 ግ፤ የሱፍ ዘይት 30 ግ፤ የወጥ በርበሬ 20 ግ፤ ነጭ ሽንኩርት 10 ግ",
    "R018": "የበሬ ስጋ 800 ግ፤ ቀይ ሽንኩርት 160 ግ፤ ቃሪያ 140 ግ፤ ቲማቲም 80 ግ፤ የሱፍ ዘይት 30 ግ፤ ነጭ ሽንኩርት 8 ግ",
    "R019": "የዶሮ ደረት ስጋ 800 ግ፤ ቀይ ሽንኩርት 160 ግ፤ ቃሪያ 140 ግ፤ ቲማቲም 80 ግ፤ የሱፍ ዘይት 25 ግ፤ ነጭ ሽንኩርት 8 ግ",
    "R020": "የተፈጨ የበሬ ስጋ 800 ግ፤ ቀይ ሽንኩርት 350 ግ፤ ቲማቲም 160 ግ፤ የሱፍ ዘይት 30 ግ፤ የወጥ በርበሬ 15 ግ፤ ነጭ ሽንኩርት 10 ግ",
    "R021": "የበሰለ እንቁላል 400 ግ፤ እንጀራ 400 ግ፤ ቀይ ሽንኩርት 150 ግ፤ ቲማቲም 180 ግ፤ የሱፍ ዘይት 20 ግ፤ የወጥ በርበሬ 10 ግ",
    "R022": "የበሬ ስጋ 800 ግ፤ ንጥር ቅቤ 30 ግ፤ ሚጥሚጣ እና ቅመም 5 ግ",
    "R023": "የበሬ ስጋ 700 ግ፤ የተቀቀለ ድንች 400 ግ፤ ቀይ ሽንኩርት 250 ግ፤ ካሮት 150 ግ፤ የሱፍ ዘይት 20 ግ፤ ነጭ ሽንኩርት 8 ግ",
    "R024": "የአበሻ አይብ 600 ግ፤ የጎመን ቅጠል 450 ግ፤ ቀይ ሽንኩርት 100 ግ፤ የሱፍ ዘይት 15 ግ፤ የሎሚ ጭማቂ 25 ግ",
    "R025": "የግሪክ እርጎ 800 ግ፤ አጃ (ኦትስ) 160 ግ፤ ሙዝ 400 ግ፤ የተቆላ ለውዝ 60 ግ",
    "R026": "የዶሮ ደረት ስጋ 600 ግ፤ የበሰለ ቡናማ ሩዝ 800 ግ፤ የበሰለ ብሮኮሊ 250 ግ፤ ቃሪያ 120 ግ፤ የወይራ ዘይት 20 ግ፤ የሎሚ ጭማቂ 30 ግ",
    "R027": "የታሸገ ቱና 600 ግ፤ የሙሉ ስንዴ ፓስታ 800 ግ፤ ቲማቲም 100 ግ፤ ኪያር 80 ግ፤ የወይራ ዘይት 20 ግ",
    "R028": "የበሰለ እንቁላል 300 ግ፤ የሙሉ ስንዴ ዳቦ 400 ግ፤ አቮካዶ 250 ግ",
}

# ==========================================
# 6. RESOLUTION HELPERS
# ==========================================
def get_food_name(food_id: str, default_name: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    pair = FOOD_GLOSSARY.get(food_id)
    if pair:
        return pair[1] if lang == "AM" else pair[0]
    if lang == "AM" and default_name:
        dn = default_name.strip().lower()
        for fid, (en, am) in FOOD_GLOSSARY.items():
            if en.lower() == dn:
                return am
        for rid, (en, am) in RECIPE_GLOSSARY.items():
            if en.lower() == dn or en.replace("Coach Hilawe ", "").lower() == dn:
                return am
    return default_name


def get_recipe_name(recipe_id: str, default_name: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    pair = RECIPE_GLOSSARY.get(recipe_id)
    if pair:
        return pair[1] if lang == "AM" else pair[0]
    if lang == "AM" and default_name:
        dn = default_name.strip().lower()
        for rid, (en, am) in RECIPE_GLOSSARY.items():
            if en.lower() == dn or en.replace("Coach Hilawe ", "").lower() == dn:
                return am
    return default_name


def get_template_name(template_id: str, default_name: str, language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    pair = TEMPLATE_GLOSSARY.get(template_id)
    if pair:
        return pair[1] if lang == "AM" else pair[0]
    return default_name


def get_recipe_method(recipe_id: str, default_method: str = "", language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    if lang == "AM":
        return RECIPE_METHODS_AM.get(recipe_id, default_method)
    return default_method


def get_recipe_summary(recipe_id: str, default_summary: str = "", language: str = "EN") -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    if lang == "AM":
        return RECIPE_SUMMARIES_AM.get(recipe_id, default_summary)
    return default_summary


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

