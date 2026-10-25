import re

content = open('meal_plan/glossary.py', 'r', encoding='utf-8').read()

terms = [
    'የሀገር ባህል አይብ',
    'የተዘጋጀ እንጀራ',
    'የበሬ ስጋ አልጫ',
    'ስረ-መሬት አትክልቶች',
    'ቅባት አልባ የእንስሳት ፕሮቲን',
    'የተጨመረ ቅባት እና ዘይት',
    'እህል እና ስታርች',
    'የጥራጥሬ ዱቄት (ሽሮ)',
    'የዕፅዋት ፕሮቲን እና አኩሪ አተር',
    'ሙሉ እንቁላል (የበሰለ)',
    'የእንቁላል ነጭ ክፍል (የበሰለ)'
]

for t in terms:
    count = content.count(t)
    if count:
        print(f"glossary.py has {count} instances of {t}")

dataset_path = 'meal_plan/data/hilawe_v1_3_dataset.json'
try:
    ds_content = open(dataset_path, 'r', encoding='utf-8').read()
    for t in terms:
        count = ds_content.count(t)
        if count:
            print(f"dataset.json has {count} instances of {t}")
except Exception as e:
    print(f"dataset.json error: {e}")
