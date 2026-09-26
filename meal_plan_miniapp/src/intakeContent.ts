import type { Language } from './api'

export type Option = { value: string; title: string; body?: string; icon?: string }

export type FoodOption = Option & {
  popular?: boolean
  category?: 'GRAINS' | 'LEGUMES' | 'PROTEIN' | 'VEGETABLES' | 'FRUITS' | 'FATS'
}

export const foodOptions: Record<Language, FoodOption[]> = {
  AM: [
    // 16 Core Staples (featured upfront)
    { value: 'INJERA', title: 'እንጀራ', popular: true, category: 'GRAINS' },
    { value: 'SHIRO', title: 'ሽሮ', popular: true, category: 'LEGUMES' },
    { value: 'MISIR', title: 'ምስር', popular: true, category: 'LEGUMES' },
    { value: 'EGGS', title: 'እንቁላል', popular: true, category: 'PROTEIN' },
    { value: 'CHICKEN', title: 'ዶሮ', popular: true, category: 'PROTEIN' },
    { value: 'BEEF', title: 'ስጋ / ጥብስ', popular: true, category: 'PROTEIN' },
    { value: 'FISH', title: 'ዓሳ (ቲላፒያ)', popular: true, category: 'PROTEIN' },
    { value: 'MILK_YOGURT', title: 'ወተት / እርጎ', popular: true, category: 'PROTEIN' },
    { value: 'RICE', title: 'ሩዝ (ነጭ/ቡናማ)', popular: true, category: 'GRAINS' },
    { value: 'OATS', title: 'አጃ (Oats)', popular: true, category: 'GRAINS' },
    { value: 'POTATO', title: 'ድንች', popular: true, category: 'GRAINS' },
    { value: 'AVOCADO', title: 'አቮካዶ', popular: true, category: 'FATS' },
    { value: 'GOMEN', title: 'ጎመን', popular: true, category: 'VEGETABLES' },
    { value: 'PASTA', title: 'ፓስታ', popular: true, category: 'GRAINS' },
    { value: 'CHICKPEAS', title: 'ሽምብራ', popular: true, category: 'LEGUMES' },
    { value: 'FRUIT', title: 'ፍራፍሬ (አጠቃላይ)', popular: true, category: 'FRUITS' },

    // Extended Database Foods — Grains & Starches
    { value: 'SWEET_POTATO', title: 'ስኳር ድንች', category: 'GRAINS' },
    { value: 'BREAD', title: 'የስንዴ ዳቦ', category: 'GRAINS' },
    { value: 'CORN', title: 'በቆሎ', category: 'GRAINS' },
    { value: 'BARLEY', title: 'ገብስ / ቅንጬ', category: 'GRAINS' },
    { value: 'BULGUR', title: 'ቡልጉር', category: 'GRAINS' },
    { value: 'QUINOA', title: 'ኪኖዋ', category: 'GRAINS' },
    { value: 'KOCHO', title: 'ቆጮ', category: 'GRAINS' },
    { value: 'KITA', title: 'የስንዴ ቂጣ', category: 'GRAINS' },
    { value: 'TEFF', title: 'የጤፍ ዱቄት', category: 'GRAINS' },

    // Extended Database Foods — Legumes & Plant Proteins
    { value: 'SPLIT_PEAS', title: 'ክክ', category: 'LEGUMES' },
    { value: 'FAVA_BEANS', title: 'ፉል / ባቄላ', category: 'LEGUMES' },
    { value: 'KIDNEY_BEANS', title: 'ቀይ ቦሎቄ', category: 'LEGUMES' },
    { value: 'BLACK_BEANS', title: 'ጥቁር ቦሎቄ', category: 'LEGUMES' },
    { value: 'WHITE_BEANS', title: 'ነጭ ቦሎቄ', category: 'LEGUMES' },
    { value: 'GREEN_PEAS', title: 'አተር', category: 'LEGUMES' },
    { value: 'SOY_CHUNKS', title: 'የሶያ ስጋ', category: 'LEGUMES' },
    { value: 'TOFU', title: 'ቶፉ (የአኩሪ አተር አይብ)', category: 'LEGUMES' },
    { value: 'TEMPEH', title: 'ቴምፔ', category: 'LEGUMES' },
    { value: 'KOLO', title: 'የተቆላ ሽምብራ (ቆሎ)', category: 'LEGUMES' },

    // Extended Database Foods — Animal Proteins & Dairy
    { value: 'EGG_WHITES', title: 'የእንቁላል ነጭ ክፍል', category: 'PROTEIN' },
    { value: 'TUNA', title: 'ቱና', category: 'PROTEIN' },
    { value: 'SALMON', title: 'ሳልሞን', category: 'PROTEIN' },
    { value: 'SARDINES', title: 'ሰርዲን', category: 'PROTEIN' },
    { value: 'GOAT_MEAT', title: 'የፍየል ስጋ', category: 'PROTEIN' },
    { value: 'LAMB', title: 'የበግ ስጋ', category: 'PROTEIN' },
    { value: 'TURKEY', title: 'የቱርክ ስጋ', category: 'PROTEIN' },
    { value: 'GREEK_YOGURT', title: 'የግሪክ እርጎ', category: 'PROTEIN' },
    { value: 'AYIB', title: 'አይብ (የሀገር ባህል)', category: 'PROTEIN' },
    { value: 'COTTAGE_CHEESE', title: 'ኮቴጅ ቺዝ', category: 'PROTEIN' },

    // Extended Database Foods — Vegetables
    { value: 'CABBAGE', title: 'ጥቅል ጎመን', category: 'VEGETABLES' },
    { value: 'CARROT', title: 'ካሮት', category: 'VEGETABLES' },
    { value: 'GREEN_BEANS', title: 'ፎሶሊያ', category: 'VEGETABLES' },
    { value: 'BELL_PEPPER', title: 'ቃሪያ / የፈረንጅ ቃሪያ', category: 'VEGETABLES' },
    { value: 'BROCCOLI', title: 'ብሮኮሊ', category: 'VEGETABLES' },
    { value: 'SPINACH', title: 'ስፒናች', category: 'VEGETABLES' },
    { value: 'CUCUMBER', title: 'ኪያር', category: 'VEGETABLES' },
    { value: 'LETTUCE', title: 'ሰላጣ', category: 'VEGETABLES' },
    { value: 'ZUCCHINI', title: 'ዙኪኒ', category: 'VEGETABLES' },
    { value: 'MUSHROOMS', title: 'እንጉዳይ', category: 'VEGETABLES' },
    { value: 'BEETROOT', title: 'ቀይ ስር', category: 'VEGETABLES' },
    { value: 'CAULIFLOWER', title: 'አበባ ጎመን', category: 'VEGETABLES' },
    { value: 'EGGPLANT', title: 'ደበርጃን / የእንቁላል ተክል', category: 'VEGETABLES' },
    { value: 'OKRA', title: 'ባሚያ', category: 'VEGETABLES' },
    { value: 'TOMATO', title: 'ቲማቲም', category: 'VEGETABLES' },
    { value: 'ONION', title: 'ቀይ ሽንኩርት', category: 'VEGETABLES' },
    { value: 'GARLIC', title: 'ነጭ ሽንኩርት', category: 'VEGETABLES' },

    // Extended Database Foods — Fruits
    { value: 'BANANA', title: 'ሙዝ', category: 'FRUITS' },
    { value: 'APPLE', title: 'ፖም / አፕል', category: 'FRUITS' },
    { value: 'ORANGE', title: 'ብርቱካን', category: 'FRUITS' },
    { value: 'MANGO', title: 'ማንጎ', category: 'FRUITS' },
    { value: 'PAPAYA', title: 'ፓፓያ', category: 'FRUITS' },
    { value: 'PINEAPPLE', title: 'አናናስ', category: 'FRUITS' },
    { value: 'GUAVA', title: 'ዘይቱን / ጓቫ', category: 'FRUITS' },
    { value: 'STRAWBERRIES', title: 'ስትሮቤሪ', category: 'FRUITS' },
    { value: 'BLUEBERRIES', title: 'ብሉቤሪ', category: 'FRUITS' },
    { value: 'GRAPES', title: 'ወይን', category: 'FRUITS' },
    { value: 'WATERMELON', title: 'ሀብሀብ', category: 'FRUITS' },
    { value: 'DATES', title: 'ቴምር', category: 'FRUITS' },
    { value: 'PEACH', title: 'ኮክ', category: 'FRUITS' },

    // Extended Database Foods — Fats, Nuts & Seeds
    { value: 'PEANUTS', title: 'የተቆላ ለውዝ', category: 'FATS' },
    { value: 'PEANUT_BUTTER', title: 'የለውዝ ቅቤ', category: 'FATS' },
    { value: 'ALMONDS', title: 'አልሞንድ', category: 'FATS' },
    { value: 'WALNUTS', title: 'ዋልነት', category: 'FATS' },
    { value: 'SESAME', title: 'ሰሊጥ', category: 'FATS' },
    { value: 'CHIA_SEEDS', title: 'ቺያ ፍሬ', category: 'FATS' },
    { value: 'FLAXSEED', title: 'ተልባ', category: 'FATS' },
    { value: 'OLIVE_OIL', title: 'የወይራ ዘይት', category: 'FATS' },
    { value: 'BUTTER', title: 'ቅቤ / ንጥር ቅቤ', category: 'FATS' },
  ],
  EN: [
    // 16 Core Staples (featured upfront)
    { value: 'INJERA', title: 'Injera', popular: true, category: 'GRAINS' },
    { value: 'SHIRO', title: 'Shiro', popular: true, category: 'LEGUMES' },
    { value: 'MISIR', title: 'Misir / lentils', popular: true, category: 'LEGUMES' },
    { value: 'EGGS', title: 'Eggs', popular: true, category: 'PROTEIN' },
    { value: 'CHICKEN', title: 'Chicken', popular: true, category: 'PROTEIN' },
    { value: 'BEEF', title: 'Beef / tibs', popular: true, category: 'PROTEIN' },
    { value: 'FISH', title: 'Fish (tilapia)', popular: true, category: 'PROTEIN' },
    { value: 'MILK_YOGURT', title: 'Milk / yogurt', popular: true, category: 'PROTEIN' },
    { value: 'RICE', title: 'Rice (white/brown)', popular: true, category: 'GRAINS' },
    { value: 'OATS', title: 'Oats', popular: true, category: 'GRAINS' },
    { value: 'POTATO', title: 'Potato', popular: true, category: 'GRAINS' },
    { value: 'AVOCADO', title: 'Avocado', popular: true, category: 'FATS' },
    { value: 'GOMEN', title: 'Gomen / kale', popular: true, category: 'VEGETABLES' },
    { value: 'PASTA', title: 'Pasta', popular: true, category: 'GRAINS' },
    { value: 'CHICKPEAS', title: 'Chickpeas', popular: true, category: 'LEGUMES' },
    { value: 'FRUIT', title: 'Fruit (general)', popular: true, category: 'FRUITS' },

    // Extended Database Foods — Grains & Starches
    { value: 'SWEET_POTATO', title: 'Sweet potato', category: 'GRAINS' },
    { value: 'BREAD', title: 'Whole-wheat bread', category: 'GRAINS' },
    { value: 'CORN', title: 'Corn', category: 'GRAINS' },
    { value: 'BARLEY', title: 'Barley / kinche', category: 'GRAINS' },
    { value: 'BULGUR', title: 'Bulgur', category: 'GRAINS' },
    { value: 'QUINOA', title: 'Quinoa', category: 'GRAINS' },
    { value: 'KOCHO', title: 'Kocho', category: 'GRAINS' },
    { value: 'KITA', title: 'Kita flatbread', category: 'GRAINS' },
    { value: 'TEFF', title: 'Teff flour', category: 'GRAINS' },

    // Extended Database Foods — Legumes & Plant Proteins
    { value: 'SPLIT_PEAS', title: 'Split peas (kik)', category: 'LEGUMES' },
    { value: 'FAVA_BEANS', title: 'Ful / fava beans', category: 'LEGUMES' },
    { value: 'KIDNEY_BEANS', title: 'Kidney beans', category: 'LEGUMES' },
    { value: 'BLACK_BEANS', title: 'Black beans', category: 'LEGUMES' },
    { value: 'WHITE_BEANS', title: 'White beans', category: 'LEGUMES' },
    { value: 'GREEN_PEAS', title: 'Green peas', category: 'LEGUMES' },
    { value: 'SOY_CHUNKS', title: 'Soy chunks', category: 'LEGUMES' },
    { value: 'TOFU', title: 'Tofu', category: 'LEGUMES' },
    { value: 'TEMPEH', title: 'Tempeh', category: 'LEGUMES' },
    { value: 'KOLO', title: 'Roasted chickpeas (kolo)', category: 'LEGUMES' },

    // Extended Database Foods — Animal Proteins & Dairy
    { value: 'EGG_WHITES', title: 'Egg whites', category: 'PROTEIN' },
    { value: 'TUNA', title: 'Tuna', category: 'PROTEIN' },
    { value: 'SALMON', title: 'Salmon', category: 'PROTEIN' },
    { value: 'SARDINES', title: 'Sardines', category: 'PROTEIN' },
    { value: 'GOAT_MEAT', title: 'Goat meat', category: 'PROTEIN' },
    { value: 'LAMB', title: 'Lamb', category: 'PROTEIN' },
    { value: 'TURKEY', title: 'Turkey breast', category: 'PROTEIN' },
    { value: 'GREEK_YOGURT', title: 'Greek yogurt', category: 'PROTEIN' },
    { value: 'AYIB', title: 'Ayib / fresh cheese', category: 'PROTEIN' },
    { value: 'COTTAGE_CHEESE', title: 'Cottage cheese', category: 'PROTEIN' },

    // Extended Database Foods — Vegetables
    { value: 'CABBAGE', title: 'Cabbage', category: 'VEGETABLES' },
    { value: 'CARROT', title: 'Carrot', category: 'VEGETABLES' },
    { value: 'GREEN_BEANS', title: 'Green beans (fosolia)', category: 'VEGETABLES' },
    { value: 'BELL_PEPPER', title: 'Bell pepper', category: 'VEGETABLES' },
    { value: 'BROCCOLI', title: 'Broccoli', category: 'VEGETABLES' },
    { value: 'SPINACH', title: 'Spinach', category: 'VEGETABLES' },
    { value: 'CUCUMBER', title: 'Cucumber', category: 'VEGETABLES' },
    { value: 'LETTUCE', title: 'Lettuce', category: 'VEGETABLES' },
    { value: 'ZUCCHINI', title: 'Zucchini', category: 'VEGETABLES' },
    { value: 'MUSHROOMS', title: 'Mushrooms', category: 'VEGETABLES' },
    { value: 'BEETROOT', title: 'Beetroot', category: 'VEGETABLES' },
    { value: 'CAULIFLOWER', title: 'Cauliflower', category: 'VEGETABLES' },
    { value: 'EGGPLANT', title: 'Eggplant', category: 'VEGETABLES' },
    { value: 'OKRA', title: 'Okra', category: 'VEGETABLES' },
    { value: 'TOMATO', title: 'Tomato', category: 'VEGETABLES' },
    { value: 'ONION', title: 'Onion', category: 'VEGETABLES' },
    { value: 'GARLIC', title: 'Garlic', category: 'VEGETABLES' },

    // Extended Database Foods — Fruits
    { value: 'BANANA', title: 'Banana', category: 'FRUITS' },
    { value: 'APPLE', title: 'Apple', category: 'FRUITS' },
    { value: 'ORANGE', title: 'Orange', category: 'FRUITS' },
    { value: 'MANGO', title: 'Mango', category: 'FRUITS' },
    { value: 'PAPAYA', title: 'Papaya', category: 'FRUITS' },
    { value: 'PINEAPPLE', title: 'Pineapple', category: 'FRUITS' },
    { value: 'GUAVA', title: 'Guava', category: 'FRUITS' },
    { value: 'STRAWBERRIES', title: 'Strawberries', category: 'FRUITS' },
    { value: 'BLUEBERRIES', title: 'Blueberries', category: 'FRUITS' },
    { value: 'GRAPES', title: 'Grapes', category: 'FRUITS' },
    { value: 'WATERMELON', title: 'Watermelon', category: 'FRUITS' },
    { value: 'DATES', title: 'Dates', category: 'FRUITS' },
    { value: 'PEACH', title: 'Peach', category: 'FRUITS' },

    // Extended Database Foods — Fats, Nuts & Seeds
    { value: 'PEANUTS', title: 'Peanuts', category: 'FATS' },
    { value: 'PEANUT_BUTTER', title: 'Peanut butter', category: 'FATS' },
    { value: 'ALMONDS', title: 'Almonds', category: 'FATS' },
    { value: 'WALNUTS', title: 'Walnuts', category: 'FATS' },
    { value: 'SESAME', title: 'Sesame', category: 'FATS' },
    { value: 'CHIA_SEEDS', title: 'Chia seeds', category: 'FATS' },
    { value: 'FLAXSEED', title: 'Flaxseed', category: 'FATS' },
    { value: 'OLIVE_OIL', title: 'Olive oil', category: 'FATS' },
    { value: 'BUTTER', title: 'Butter / kibbeh', category: 'FATS' },
  ],
}

export const allergyOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'PEANUTS', title: 'ለውዝ / Peanuts' }, { value: 'TREE_NUTS', title: 'የዛፍ ፍሬዎች / Tree nuts' },
    { value: 'MILK', title: 'ወተት' }, { value: 'EGGS', title: 'እንቁላል' },
    { value: 'FISH', title: 'ዓሳ' }, { value: 'SHELLFISH', title: 'Shellfish' },
    { value: 'WHEAT', title: 'ስንዴ / Wheat' }, { value: 'SOY', title: 'Soy' },
    { value: 'SESAME', title: 'ሰሊጥ / Sesame' },
  ],
  EN: [
    { value: 'PEANUTS', title: 'Peanuts' }, { value: 'TREE_NUTS', title: 'Tree nuts' },
    { value: 'MILK', title: 'Milk' }, { value: 'EGGS', title: 'Eggs' },
    { value: 'FISH', title: 'Fish' }, { value: 'SHELLFISH', title: 'Shellfish' },
    { value: 'WHEAT', title: 'Wheat' }, { value: 'SOY', title: 'Soy' },
    { value: 'SESAME', title: 'Sesame' },
  ],
}

export const intakeCopy = {
  AM: {
    chapters: ['እርስዎ', 'ግብ', 'የቀን እንቅስቃሴ', 'ምግብ', 'ጤና'],
    continue: 'ቀጥል', back: 'ተመለስ', saving: 'በማስቀመጥ ላይ…', saved: 'ተቀምጧል',
    optional: 'አማራጭ', other: 'ሌላ ካለ ይጻፉ', none: 'ምንም የለም', yes: 'አዎ', no: 'አይ',
    searchFood: 'ምግብ ይፈልጉ (ለምሳሌ፡ ሳልሞን፣ ሩዝ፣ ስፒናች...)',
    noFoodFound: 'ምንም ምግብ አልተገኘም',
    clearSearch: 'መፈለጊያውን አጽዳ',
    popularFoods: 'ተደጋጋሚ ዋና ምግቦች',
    allFoods: 'የተገኙ ምግቦች',
    selectedPills: 'የተመረጡ ምግቦች',
    clearAll: 'ሁሉንም አጽዳ',
    tapToDiscover: 'ተጨማሪ ምግቦችን ለማግኘት ከላይ ይፈልጉ',
    introTitle: 'የሰውነትዎን ሁኔታ የሚመጥን የምግብ ፕላን እንዘጋጅ።',
    introBody: 'እዚህ የምንጠይቅዎ መረጃ አጠቃላይ የDiet PDF ለመላክ አይደለም። ዕድሜዎ፣ የሰውነት መረጃዎ፣ ግብዎ፣ የቀን እንቅስቃሴዎ፣ የሚወዱት ምግብ፣ በጀትዎ እና የጾም ልምድዎ አንድ ላይ ተመልክተው ፕላኑ እንዲዘጋጅ ነው።',
    introPoints: ['ለእርስዎ ብቻ የሚዘጋጅ', 'በተግባር ሊከተሉት የሚችሉትን ምግብ የሚያስቀድም', 'ከመላኩ በፊት የሚገመገም'],
    start: 'የእኔን ግምገማ ጀምር',
    ageTitle: 'ዕድሜዎ ስንት ነው?', ageBody: 'ዕድሜ የሰውነትዎን የቀን የኃይል ፍላጎት ለመገመት ከምንጠቀምባቸው መረጃዎች አንዱ ነው።', years: 'ዓመት',
    sexTitle: 'ለአመጋገብ ስሌቱ የምንጠቀምበትን ፆታ ይምረጡ።', sexBody: 'ይህ መረጃ የቀን ካሎሪ ፍላጎትን ለመገመት ብቻ ይጠቅማል።', male: 'ወንድ', female: 'ሴት',
    bodyTitle: 'አሁን ያለዎትን የሰውነት መረጃ ያስገቡ።', bodyBody: 'ቁመትና ክብደት ትክክለኛ የካሎሪ እና የፖርሽን መነሻ ለመዘጋጀት ይረዱናል።', height: 'ቁመት', currentWeight: 'የአሁኑ ክብደት',
    goalTitle: 'ዋናው ግብዎ ምንድነው?', goalBody: 'አንድ ዋና ግብ ይምረጡ። ፕላኑ የሚዘጋጀው በዚህ አቅጣጫ ነው።',
    targetTitle: 'ወደ ምን ክብደት መድረስ ይፈልጋሉ?', targetBody: 'ይህ የረጅም ጊዜ አቅጣጫዎን ለመረዳት ነው፤ በ7፣ 14 ወይም 30 ቀን ውስጥ ይህን ሙሉ ለሙሉ እንደሚደርሱ ቃል አይገባም።', targetWeight: 'የሚፈልጉት ክብደት',
    activityTitle: 'በአብዛኛው ቀንዎ እንዴት ያልፋል?', activityBody: 'የስራዎን፣ የትምህርትዎን እና የቀን እንቅስቃሴዎን በአጠቃላይ ያስቡ።',
    trainingTitle: 'በሳምንት ስንት ቀን ይለማመዳሉ?', trainingBody: 'ከዚያም በአብዛኛው የሚያደርጉትን የልምምድ ዓይነት ይምረጡ።', daysPerWeek: 'ቀን / ሳምንት',
    cuisineTitle: 'ፕላኑ በምን ዓይነት ምግቦች ዙሪያ እንዲገነባ ይፈልጋሉ?', cuisineBody: 'የሚኖሩበት አገር እና የሚወዱት የምግብ ባህል ሁለት የተለያዩ ነገሮች ናቸው።',
    dietaryTitle: 'በአጠቃላይ የሚከተሉት የአመጋገብ አይነት የትኛው ነው?', dietaryBody: 'ይህ ስጋ፣ ዓሳ፣ ወተት እና እንቁላል በፕላኑ ውስጥ መግባት እንደሚችሉ ለመወሰን ይረዳናል። የኦርቶዶክስ ጾምን በቀጣዩ ደረጃ በተለየ እንጠይቃለን።',
    budgetTitle: 'የግሮሰሪ በጀትዎን የሚመጥነው የትኛው ነው?', budgetBody: 'ይህ ለፕላኑ የምግብ ምርጫ ብቻ ይጠቅማል፤ የሚከፍሉትን የMeal Plan ዋጋ አይቀይርም።',
    fastingTitle: 'የኢትዮጵያ ኦርቶዶክስ ጾም ይጾማሉ?', fastingBody: 'ጾም ካለ የምግብ ምርጫዎች በተገቢው ቀን እንዲለወጡ ይህን መረጃ እንጠቀማለን።', fishFast: 'በጾም ወቅት ዓሳ ይመገባሉ?',
    likesTitle: 'በፕላንዎ ውስጥ ብዙ ጊዜ ማየት የሚወዱትን ምግቦች ይምረጡ።', likesBody: 'ይህ ግዴታ አይደለም። የመረጡትን ምግብ ከግብዎ እና ከአመጋገብ ፍላጎትዎ ጋር ሲመጣጠን ቅድሚያ ለመስጠት ይረዳናል።',
    dislikesTitle: 'ፕላንዎ ውስጥ ማየት የማይፈልጉት ምግብ አለ?', dislikesBody: 'የማይወዱትን ምግብ ይምረጡ። ይህ ከአለርጂ የተለየ ነው።',
    allergiesTitle: 'የምግብ አለርጂ አለዎት?', allergiesBody: '“አልወደውም” ከማለት የተለየ ነው። አለርጂ የሚያመጣብዎትን ምግብ በትክክል ይምረጡ ወይም ይጻፉ።', severeAllergy: 'ከእነዚህ አለርጂዎች አንዱ ከባድ ምላሽ (anaphylaxis / emergency reaction) አስከትሎብዎት ያውቃል?',
    intoleranceTitle: 'አለርጂ ሳይሆን ሰውነትዎን የሚያስቸግር ምግብ አለ?', intoleranceBody: 'ለምሳሌ ሆድ መነፋት፣ ህመም ወይም ሌላ አለመመቸት የሚያመጣ ምግብ።',
    healthIntro: 'የጤና ማረጋገጫ', healthBody: 'ከመክፈልዎ በፊት ፕላኑ በአውቶሜሽን መቀጠል ይችላል ወይስ ተጨማሪ የሰው ግምገማ ያስፈልገዋል ለማወቅ ጥቂት የጤና ጥያቄዎች አሉ። “አዎ” ማለት ከአገልግሎቱ ተቀባይነት አያስወጣዎትም፤ ተጨማሪ ግምገማ ማለት ነው።',
    pregnancyQ: 'እርጉዝ ነዎት፣ በቅርቡ ወልደዋል ወይም ጡት እያጠቡ ነው?',
    eatingQ: 'ከምግብ ጋር የተያያዘ የአመጋገብ መዛባት (eating disorder) ችግር አለ ወይም አሳሳቢ ታሪክ አለ?',
    kidneyQ: 'የኩላሊት ወይም የጉበት ህመም በሐኪም ተነግሮዎታል?',
    diabetesQ: 'Diabetes አለዎት ወይም የደም ስኳርን የሚቆጣጠር መድሃኒት ይወስዳሉ?',
    clinicianDietQ: 'ሐኪም ወይም ባለሙያ እንዲከተሉት የሰጠዎት የተለየ የአመጋገብ መመሪያ (prescribed diet) አለ?',
    giQ: 'ከባድ ወይም ቀጣይ የሆድ/አንጀት ህመም ወይም ህመም ምልክት አለ?',
    unexplainedQ: 'ምክንያቱ ሳይታወቅ በቅርቡ ክብደትዎ በጣም ጨምሯል ወይም ቀንሷል?',
    otherHealthQ: 'ፕላኑ ከመዘጋጀቱ በፊት ማወቅ ያለብን ሌላ አስፈላጊ የጤና ለውጥ ወይም ሁኔታ አለ?',
    otherHealthDetails: 'በአጭሩ ይግለጹ',
    completeTitle: 'ግምገማዎ ተጠናቋል።', completeBody: 'የሰጡን መረጃ በደህንነት ተቀምጧል። ቀጣዩ ደረጃ የጤና ጌቱን ማረጋገጥ እና የካሎሪ/ፕሮቲን መነሻዎን ማስላት ነው።', completeDemo: 'Phase 3 እዚህ ያበቃል። ክፍያ ወይም Meal Plan generation ገና አልተጀመረም።',
  },
  EN: {
    chapters: ['You', 'Goal', 'Daily life', 'Food', 'Health'],
    continue: 'Continue', back: 'Back', saving: 'Saving…', saved: 'Saved', optional: 'Optional', other: 'Add something else', none: 'None', yes: 'Yes', no: 'No',
    searchFood: 'Search foods (e.g. salmon, rice, spinach...)',
    noFoodFound: 'No foods found matching your search',
    clearSearch: 'Clear search',
    popularFoods: 'Popular staple foods',
    allFoods: 'Matching foods',
    selectedPills: 'Selected foods',
    clearAll: 'Clear all',
    tapToDiscover: 'Search above to discover 50+ database foods',
    introTitle: 'Let’s build a meal plan around your real life.',
    introBody: 'This assessment is not here to send you a generic diet PDF. We use your body data, goal, daily activity, food preferences, budget and fasting choices together so the plan can be prepared around you.',
    introPoints: ['Prepared specifically for your profile', 'Prioritizes food you can realistically follow', 'Reviewed before it is released'],
    start: 'Start my assessment',
    ageTitle: 'How old are you?', ageBody: 'Age is one of the inputs used later to estimate your daily energy needs.', years: 'years',
    sexTitle: 'Choose the sex used for the nutrition calculation.', sexBody: 'This is used only as an input when estimating your daily energy requirement.', male: 'Male', female: 'Female',
    bodyTitle: 'Enter your current body information.', bodyBody: 'Height and current weight help establish a useful starting point for calories and portions.', height: 'Height', currentWeight: 'Current weight',
    goalTitle: 'What is your main goal?', goalBody: 'Choose one primary direction. The plan will be built around this goal.',
    targetTitle: 'What body weight are you ultimately working toward?', targetBody: 'This gives us long-term direction. It is not a promise that you will reach the entire target during a 7, 14 or 30-day plan.', targetWeight: 'Target weight',
    activityTitle: 'What does a normal day look like for you?', activityBody: 'Think about work, school and how much you normally move outside training.',
    trainingTitle: 'How many days per week do you normally train?', trainingBody: 'Then choose the type of training you do most often.', daysPerWeek: 'days / week',
    cuisineTitle: 'What kind of food should your plan be built around?', cuisineBody: 'Where you live and the cuisine you prefer are two different things.',
    dietaryTitle: 'Which dietary pattern best describes how you eat?', dietaryBody: 'This tells the engine whether meat, fish, dairy and eggs may be used. Ethiopian Orthodox fasting is asked separately on the next steps.',
    budgetTitle: 'Which grocery-budget style fits you best?', budgetBody: 'This affects food selection only. It does not change the price of the Meal Plan service.',
    fastingTitle: 'Do you follow Ethiopian Orthodox fasting?', fastingBody: 'We use this so food choices can change appropriately on fasting days.', fishFast: 'Do you eat fish while fasting?',
    likesTitle: 'Which foods would you enjoy seeing more often in your plan?', likesBody: 'Optional. When they fit your nutrition needs, selected foods can receive preference in the meal engine.',
    dislikesTitle: 'Which foods do you not want in your plan?', dislikesBody: 'Select foods you simply dislike. Allergies are handled separately.',
    allergiesTitle: 'Do you have any food allergies?', allergiesBody: 'This is different from disliking a food. Select or type foods that cause an allergic reaction.', severeAllergy: 'Has any food allergy ever caused a severe/anaphylactic or emergency reaction?',
    intoleranceTitle: 'Any foods that cause discomfort or intolerance rather than an allergy?', intoleranceBody: 'For example bloating, pain or another repeatable reaction.',
    healthIntro: 'Health check', healthBody: 'Before payment, these answers help determine whether automation can continue normally or your profile needs additional human review. A “Yes” does not automatically exclude you; it means extra review may be required.',
    pregnancyQ: 'Are you pregnant, recently postpartum, or currently breastfeeding?',
    eatingQ: 'Do you have an eating-disorder concern or an important history of disordered eating?',
    kidneyQ: 'Have you been diagnosed with kidney or liver disease?',
    diabetesQ: 'Do you have diabetes or take medication that affects blood glucose?',
    clinicianDietQ: 'Are you currently following a diet prescribed by a clinician or qualified health professional?',
    giQ: 'Do you have a severe or persistent gastrointestinal condition or symptoms?',
    unexplainedQ: 'Have you had a recent significant weight change without a clear explanation?',
    otherHealthQ: 'Is there any other important health change or condition we should know before preparing your plan?',
    otherHealthDetails: 'Briefly describe it',
    completeTitle: 'Your assessment is complete.', completeBody: 'Your answers have been saved. The next phase will evaluate the Coach Hilawe health gate and calculate your calorie/protein starting profile.', completeDemo: 'Phase 3 stops here. No payment or meal generation has started yet.',
  },
} as const

export const goalOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'FAT_LOSS', title: 'ስብ መቀነስ', body: 'የሰውነት ስብን በቀስታ እየቀነሱ ጡንቻን ለመጠበቅ።' },
    { value: 'MUSCLE_GAIN', title: 'ጡንቻ መጨመር', body: 'ጡንቻ ለመገንባት በቂ ኃይል እና ፕሮቲን ማግኘት።' },
    { value: 'RECOMPOSITION', title: 'Body Recomposition', body: 'ጡንቻን እያጠናከሩ ስብን በቀስታ ለመቀነስ።' },
    { value: 'MAINTAIN', title: 'ክብደት መጠበቅ', body: 'የአሁኑን ክብደት በመጠበቅ የተረጋጋ የአመጋገብ ልምድ ለመገንባት።' },
    { value: 'PERFORMANCE', title: 'ጥንካሬ / Performance', body: 'ልምምድ፣ ኃይል እና recovery ለመደገፍ።' },
  ],
  EN: [
    { value: 'FAT_LOSS', title: 'Lose body fat', body: 'Create a controlled deficit while protecting muscle.' },
    { value: 'MUSCLE_GAIN', title: 'Build muscle', body: 'Support muscle growth with enough energy and protein.' },
    { value: 'RECOMPOSITION', title: 'Body recomposition', body: 'Build/maintain muscle while gradually reducing fat.' },
    { value: 'MAINTAIN', title: 'Maintain weight', body: 'Maintain body weight and build consistent eating habits.' },
    { value: 'PERFORMANCE', title: 'Strength / performance', body: 'Support training performance, energy and recovery.' },
  ],
}

export const activityOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'MOSTLY_SEATED', title: 'አብዛኛውን ጊዜ እቀመጣለሁ', body: 'የቢሮ ስራ፣ ትምህርት፣ መኪና መንዳት ወይም ብዙ ጊዜ ተቀምጦ የሚደረግ ስራ።' },
    { value: 'LIGHTLY_ACTIVE', title: 'ቀላል እንቅስቃሴ አለኝ', body: 'በቀን ውስጥ መራመድ እና ትንሽ እንቅስቃሴ አለ።' },
    { value: 'ACTIVE', title: 'ንቁ ነኝ', body: 'ብዙ መንቀሳቀስ እና/ወይም ተደጋጋሚ ልምምድ።' },
    { value: 'VERY_ACTIVE', title: 'በጣም ንቁ ነኝ', body: 'አካላዊ ስራ፣ ከፍተኛ እንቅስቃሴ ወይም ብዙ ጊዜ ከባድ ልምምድ።' },
  ],
  EN: [
    { value: 'MOSTLY_SEATED', title: 'Mostly seated', body: 'Office work, studying, driving or a mostly seated day.' },
    { value: 'LIGHTLY_ACTIVE', title: 'Lightly active', body: 'Some regular walking and movement during the day.' },
    { value: 'ACTIVE', title: 'Active', body: 'Frequent movement and/or regular training.' },
    { value: 'VERY_ACTIVE', title: 'Very active', body: 'Physical work, high daily movement or frequent hard training.' },
  ],
}

export const trainingOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'GYM_STRENGTH', title: 'Gym / Strength' }, { value: 'RUNNING_CARDIO', title: 'Running / Cardio' },
    { value: 'SPORTS', title: 'Sports' }, { value: 'HOME_WORKOUT', title: 'Home workout' },
    { value: 'MIXED', title: 'Mixed' }, { value: 'NOT_TRAINING', title: 'አሁን አልለማመድም' },
  ],
  EN: [
    { value: 'GYM_STRENGTH', title: 'Gym / strength' }, { value: 'RUNNING_CARDIO', title: 'Running / cardio' },
    { value: 'SPORTS', title: 'Sports' }, { value: 'HOME_WORKOUT', title: 'Home workout' },
    { value: 'MIXED', title: 'Mixed' }, { value: 'NOT_TRAINING', title: 'I do not currently train' },
  ],
}

export const cuisineOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'ETHIOPIAN', title: 'በአብዛኛው የኢትዮጵያ ምግብ', icon: 'ET' },
    { value: 'MIXED', title: 'የኢትዮጵያ + ዓለም አቀፍ ቅልቅል', icon: 'MIX' },
    { value: 'INTERNATIONAL', title: 'በአብዛኛው ዓለም አቀፍ ምግብ', icon: 'INT' },
  ],
  EN: [
    { value: 'ETHIOPIAN', title: 'Mostly Ethiopian', icon: 'ET' },
    { value: 'MIXED', title: 'Ethiopian + international mix', icon: 'MIX' },
    { value: 'INTERNATIONAL', title: 'Mostly international', icon: 'INT' },
  ],
}

export const dietaryPatternOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'OMNIVORE', title: 'ስጋና የእንስሳት ምግቦችን እመገባለሁ', body: 'ስጋ፣ ዓሳ፣ እንቁላል እና ወተት ምርቶች ሊካተቱ ይችላሉ።' },
    { value: 'VEGETARIAN', title: 'Vegetarian — ስጋ/ዓሳ አልበላም', body: 'እንቁላልና ወተት ምርቶች ሊካተቱ ይችላሉ፤ ስጋና ዓሳ አይካተቱም።' },
    { value: 'VEGAN', title: 'Vegan — ከእንስሳት የሚመጣ ምግብ አልበላም', body: 'ስጋ፣ ዓሳ፣ ወተት እና እንቁላል አይካተቱም።' },
  ],
  EN: [
    { value: 'OMNIVORE', title: 'Omnivore', body: 'Meat, fish, eggs and dairy may be included.' },
    { value: 'VEGETARIAN', title: 'Vegetarian', body: 'Lacto-ovo vegetarian: eggs and dairy may be included; meat and fish are excluded.' },
    { value: 'VEGAN', title: 'Vegan', body: 'Meat, fish, dairy and eggs are excluded.' },
  ],
}

export const budgetOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'SAVE', title: 'SAVE', body: 'በቀላሉ የሚገኙ እና በጀትን የሚጠብቁ የዕለት ተዕለት ምግቦችን ቅድሚያ ይሰጣል።' },
    { value: 'BALANCED', title: 'BALANCED', body: 'ዋጋን እና የምግብ ልዩነትን በመካከለኛ ሁኔታ ያመጣጥናል።' },
    { value: 'FLEXIBLE', title: 'FLEXIBLE', body: 'የምግብ ልዩነት ከዋጋ በላይ ቅድሚያ ሲኖረው።' },
  ],
  EN: [
    { value: 'SAVE', title: 'SAVE', body: 'Prioritize accessible everyday foods and value.' },
    { value: 'BALANCED', title: 'BALANCED', body: 'Balance reasonable grocery cost with good variety.' },
    { value: 'FLEXIBLE', title: 'FLEXIBLE', body: 'Prioritize wider food variety when useful.' },
  ],
}

export const fastingOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'NONE', title: 'አልጾምም' },
    { value: 'WED_FRI', title: 'ረቡዕ እና አርብ' },
    { value: 'SEASONAL', title: 'ረጅም / ወቅታዊ ጾሞች' },
    { value: 'WED_FRI_AND_SEASONAL', title: 'ረቡዕ/አርብ + ረጅም ጾሞች' },
  ],
  EN: [
    { value: 'NONE', title: 'I do not fast' },
    { value: 'WED_FRI', title: 'Wednesday & Friday' },
    { value: 'SEASONAL', title: 'Long / seasonal fasting periods' },
    { value: 'WED_FRI_AND_SEASONAL', title: 'Wednesday/Friday + long fasts' },
  ],
}
