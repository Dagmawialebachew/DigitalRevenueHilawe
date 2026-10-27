import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import config, asyncpg

async def check():
    conn = await asyncpg.connect(config.settings.DATABASE_URL)
    rows = await conn.fetch('''
        SELECT id, title, language, gender, level, frequency, price, is_active 
        FROM products 
        ORDER BY language, gender, level, frequency, id
    ''')
    for r in rows:
        print(f"{r['id']:<3} | {r['language']:<3} | {r['gender']:<7} | {r['level']:<15} | Freq: {r['frequency']} | Price: {r['price']} | Active: {r['is_active']} | {r['title'][:35]}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
