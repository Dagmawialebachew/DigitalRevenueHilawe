import asyncio, aiohttp, os, io, json
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
gemini_key = os.getenv("gemini_api_key")

async def get_tg_file(file_id: str) -> bytes | None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if not data.get("ok"):
                return None
            file_path = data["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            async with session.get(download_url) as img_resp:
                return await img_resp.read()

async def analyze_receipt_with_gemini(img_bytes: bytes) -> dict:
    client = genai.Client(api_key=gemini_key)
    prompt = """Analyze this Ethiopian bank payment receipt/SMS screenshot.
Extract:
1. bank: e.g. "CBE", "Telebirr", "Bank of Abyssinia", "Dashen", "Awash", "CBE Birr", or "Unknown"
2. reference_id: exact transaction code (e.g. FT..., DH..., etc.)
3. payer_name: person who sent money
4. receiver_name: recipient person or account
5. amount_settled: exact numerical amount transferred in ETB
6. date_time: date and time of transaction
7. is_legitimate: boolean, whether this looks like a genuine payment receipt
8. notes: any anomalies, photoshop signs, or comments

Respond in pure valid JSON without markdown wrapping."""

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            prompt
        ]
    )
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

async def run_sample():
    # Test with PID #691 (Muaz Ahmed, 949 ETB, rejected)
    import asyncpg
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        row = await conn.fetchrow("SELECT id, amount, status, proof_file_id FROM payments WHERE id = 691")
        print(f"Testing PID #{row['id']} (DB Status: {row['status']}, DB Amt: {row['amount']})")
        img_bytes = await get_tg_file(row['proof_file_id'])
        if img_bytes:
            print("Downloaded image from Telegram. Analyzing with Gemini 3.8 Flash...")
            analysis = await analyze_receipt_with_gemini(img_bytes)
            print("Gemini Analysis Result:")
            print(json.dumps(analysis, indent=2))
        else:
            print("Failed to download image from Telegram.")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(run_sample())
