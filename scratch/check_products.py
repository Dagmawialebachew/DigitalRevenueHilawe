import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def main():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    products = await db.fetch("SELECT id, language, gender, level, frequency, price FROM products ORDER BY id")
    print(f"Total products: {len(products)}")
    for p in products:
        print(f"ID: {p['id']}, Lang: {p['language']}, Gender: {p['gender']}, Level: {p['level']}, Freq: {p['frequency']}, Price: {p['price']}")

if __name__ == "__main__":
    asyncio.run(main())

