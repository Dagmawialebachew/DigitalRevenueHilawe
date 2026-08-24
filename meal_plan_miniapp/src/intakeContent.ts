import type { Language } from './api'

export type Option = { value: string; title: string; body?: string; icon?: string }

export const foodOptions: Record<Language, Option[]> = {
  AM: [
    { value: 'INJERA', title: 'እንጀራ' }, { value: 'SHIRO', title: 'ሽሮ' },
    { value: 'MISIR', title: 'ምስር' }, { value: 'EGGS', title: 'እንቁላል' },
    { value: 'CHICKEN', title: 'ዶሮ' }, { value: 'BEEF', title: 'ስጋ / ጥብስ' },
    { value: 'FISH', title: 'ዓሳ' }, { value: 'MILK_YOGURT', title: 'ወተት / እርጎ' },
    { value: 'RICE', title: 'ሩዝ' }, { value: 'OATS', title: 'አጃ (Oats)' },
    { value: 'POTATO', title: 'ድንች' }, { value: 'AVOCADO', title: 'አቮካዶ' },
    { value: 'GOMEN', title: 'ጎመን' }, { value: 'PASTA', title: 'ፓስታ' },
    { value: 'CHICKPEAS', title: 'ሽምብራ' }, { value: 'FRUIT', title: 'ፍራፍሬ' },
  ],
  EN: [
    { value: 'INJERA', title: 'Injera' }, { value: 'SHIRO', title: 'Shiro' },
    { value: 'MISIR', title: 'Misir / lentils' }, { value: 'EGGS', title: 'Eggs' },
    { value: 'CHICKEN', title: 'Chicken' }, { value: 'BEEF', title: 'Beef / tibs' },
    { value: 'FISH', title: 'Fish' }, { value: 'MILK_YOGURT', title: 'Milk / yogurt' },
    { value: 'RICE', title: 'Rice' }, { value: 'OATS', title: 'Oats' },
    { value: 'POTATO', title: 'Potato' }, { value: 'AVOCADO', title: 'Avocado' },
    { value: 'GOMEN', title: 'Gomen' }, { value: 'PASTA', title: 'Pasta' },
    { value: 'CHICKPEAS', title: 'Chickpeas' }, { value: 'FRUIT', title: 'Fruit' },
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
