import os
import cv2
import pytesseract
import re
import numpy as np
import httpx
from PIL import Image
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings

import pytesseract
# Only needed for Windows users
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# --- CONFIG ---

API_KEY = os.getenv("VERIFY_API", "")
API_URL = "https://verifyapi.leulzenebe.pro/verify"
CBE_SUFFIX = "99533641"
TELEBIRR_TARGET = "0953462846"

router = Router(name="verify")

class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()
    
    
class ReceiptArchitect:
    def __init__(self):
        self.patterns = {
            'CBE': r"FT[A-Z0-9]{10}",
            'TELEBIRR': r"[A-Z0-9]{10,12}", 
            'AMOUNT': r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)" 
        }

    def preprocess_image(self, image_path):
            img = cv2.imread(image_path)
            if img is None: return None
            
            # 1. Upscale (3x is often better for thin fonts)
            img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 2. Boost Contrast (CLAHE) - Essential for dark mode CBE receipts
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            # 3. Denoise while keeping edges sharp
            gray = cv2.bilateralFilter(gray, 11, 75, 75)
            
            # 4. Otsu's Thresholding (often more stable than Adaptive for clean digital screenshots)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            temp_path = f"temp_{os.path.basename(image_path)}"
            cv2.imwrite(temp_path, thresh)
            return temp_path

    # --- THE MISSING METHOD ---
    async def verify_external(self, reference: str, provider: str):
        """Uses the Universal Endpoint as a fallback for 404s."""
        
        # We will try the Universal Endpoint first as it is 'Smart' 
        # and less likely to 404 than specific sub-routes.
        url = "https://verifyapi.leulzenebe.pro/verify" 
        
        if provider == "Telebirr":
            # Based on docs: Telebirr only requires the 'reference'
            payload = {"reference": str(reference).strip()}
        else:
            # CBE and others
            payload = {
                "reference": str(reference).strip(),
                "suffix": CBE_SUFFIX
            }

        headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # We try the universal endpoint
                response = await client.post(url, json=payload, headers=headers, timeout=20.0)
                
                # If universal fails or if you strictly want to try the other one:
                if response.status_code == 404 and provider == "Telebirr":
                    alt_url = "https://verifyapi.leulzenebe.pro/verify-telebirr/" # Added trailing slash
                    response = await client.post(alt_url, json=payload, headers=headers, timeout=20.0)

                if response.status_code != 200:
                    print(f"DEBUG: {provider} API Error ({response.status_code}): {response.text}")
                
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    def extract_local_data(self, image_path):
        processed_path = self.preprocess_image(image_path)
        if not processed_path:
            return {"provider": "Error", "ref": None, "amount": None, "raw_text": ""}
            
        # PSM 6 (Single block of text) or PSM 11 (Sparse text)
        # We also remove the whitelist restrictions to let Tesseract "guess" better, then we clean it manually
        text = pytesseract.image_to_string(Image.open(processed_path), config=r'--oem 3 --psm 6')
        
        if os.path.exists(processed_path): os.remove(processed_path)

        clean_text = text.upper()
        # Clean noise: remove obvious OCR artifacts but keep alphanumeric
        clean_text = re.sub(r'[^A-Z0-9\n\s:]', '', clean_text)
        
        result = {"ref": None, "amount": None, "provider": "Unknown", "raw_text": text}

        # 1. PROVIDER DETECTION
        if any(x in clean_text for x in ["COMMERCIAL", "CBE", "FT"]):
            result['provider'] = "CBE"
        elif "AWASH" in clean_text:
            result['provider'] = "Awash"
        elif any(x in clean_text for x in ["TELEBIRR", "SUCCESSFUL", "TRANSACTION"]):
            result['provider'] = "Telebirr"

        # 2. REFERENCE EXTRACTION
        
        # --- STAGE A: CBE (Handles the 'Black' notification and full receipts) ---
        if result['provider'] == "CBE":
            # Search for anything starting with FT (standard for CBE)
            # We allow for common misreads like 'F T' or 'FT '
            cbe_match = re.search(r"F\s?T\s?([A-Z0-9]{8,12})", clean_text)
            if cbe_match:
                result['ref'] = f"FT{cbe_match.group(1)}".replace(" ", "")
            elif "ID" in clean_text:
                # Look for digits/letters after 'ID'
                id_parts = clean_text.split("ID")[-1]
                fuzzy_id = re.findall(r"([A-Z0-9]{10,14})", id_parts)
                if fuzzy_id: result['ref'] = fuzzy_id[0]

        # --- STAGE B: TELEBIRR (The stylized font specialist) ---
        elif result['provider'] == "Telebirr":
            # If the label 'NUMBER' is found, grab the next string regardless of pattern
            if "NUMBER" in clean_text:
                # Split and grab the block after the colon or space
                after_number = clean_text.split("NUMBER")[-1].strip()
                # Find the first dense block of alphanumeric text
                # We normalize the text: Replace 'O' with '0' and 'I' with '1' for Telebirr refs
                blocks = re.findall(r"([A-Z0-9]{8,12})", after_number)
                if blocks:
                    ref_candidate = blocks[0]
                    # Common Telebirr OCR Fixes
                    ref_candidate = ref_candidate.replace(" ", "").strip()
                    print('here is the transaction id for the telebirr', ref_candidate)
                    ref_candidate = ref_candidate.replace('0', 'o').upper()
                    result['ref'] = ref_candidate

        # 3. AMOUNT EXTRACTION (Improved)
        # Look for numbers near 'ETB' or 'AMOUNT'
        amt_match = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text)
        if amt_match:
            # Usually, the largest number on the receipt is the total amount
            result['amount'] = max(amt_match, key=lambda x: len(x.replace(',', '')))

        return result

# --- UI COMPONENTS ---
def get_verifier_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📸 Upload Screenshot", callback_data="test_upload"))
    builder.row(types.InlineKeyboardButton(text="🎲 Test Batch (DB)", callback_data="test_db_random"))
    return builder.as_markup()

# --- HANDLERS ---

@router.callback_query(F.data == "test_upload")
async def start_upload_test(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🎯 **Ready!** Send me the receipt screenshot.")
    await state.set_state(PaymentStates.waiting_for_screenshot)

@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot_test(message: types.Message, state: FSMContext, bot: Bot):
    status_msg = await message.answer("🔄 **OCR: Scanning for Reference Number...**")
    
    # Download
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = f"downloads/{photo.file_id}.png"
    if not os.path.exists("downloads"): os.makedirs("downloads")
    await bot.download_file(file.file_path, file_path)

    # 1. Local Extract
    architect = ReceiptArchitect()
    local = architect.extract_local_data(file_path)

    # Inside your handle_screenshot_test function
    if not local['ref'] or len(str(local['ref'])) < 8:
        await status_msg.edit_text("⚠️ <b>Extraction Failed:</b> The OCR couldn't find a valid Ref ID. Please try a clearer photo.")
        return

    # Log exactly what you are sending to see why the API is mad
    print(f"DEBUG: Sending to API -> Ref: {local['ref']}, Suffix: {CBE_SUFFIX}, Phone: {TELEBIRR_TARGET}")


    # 2. Bank API Verify
    await status_msg.edit_text(f"📡 **API: Querying Bank for {local['ref']}...**")
    bank_data = await architect.verify_external(local['ref'], local['provider'])

    # 3. Decision Logic
    # 3. Decision Logic
    is_real = bank_data.get("success", False)
    data = bank_data.get("data", {})
    
    # Check both potential keys: 'receiver' (CBE) and 'creditedPartyName' (Telebirr)
    api_receiver = data.get("receiver") or data.get("creditedPartyName") or ""
    receiver_name = str(api_receiver).upper()
    
    is_hilawe = "HILAWE" in local['raw_text'].upper() or "HILAWE" in receiver_name
    
    # 4. Constructing the HTML Report
    # Using <b> for labels and <code> for technical strings like Ref numbers
    report = (
        "🧐 <b>VERIFICATION VERDICT</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🏦 <b>Bank:</b> <i>{local['provider']}</i>\n"
        f"🆔 <b>Ref:</b> <code>{local['ref'] or 'NOT DETECTED'}</code>\n"
        f"✅ <b>Bank Verified:</b> {'<pre>YES (Confirmed)</pre>' if is_real else '<pre>NO (Invalid)</pre>'}\n"
        f"👤 <b>Receiver:</b> {'<u>HILAWE FOUND</u>' if is_hilawe else '<i>NOT TARGETED</i>'}\n"
        "━━━━━━━━━━━━━━━\n"
    )

    if is_real and is_hilawe:
        report += "🟢 <b>RESULT:</b> <b><u>TRANSACTION VALIDATED</u></b>"
    else:
        report += "🔴 <b>RESULT:</b> <b><u>REJECTED / MANUAL REVIEW</u></b>"

    # Send the final report
    await status_msg.edit_text(report, parse_mode="HTML")
    
    # Clean up local temp file
    if os.path.exists(file_path): 
        os.remove(file_path)
    
    await state.clear()
@router.callback_query(F.data == "test_db_random")
async def test_batch_from_db(callback: types.CallbackQuery, bot: Bot, db):
    # 1. Initial Status
    status_msg = await callback.message.answer("🔍 **Fetching last 5 payments for deep audit...**")
    recent_payments = await db.get_recent_payment_proofs(5)
    
    if not recent_payments:
        return await status_msg.edit_text("❌ No payments found in DB.")

    architect = ReceiptArchitect()
    
    # 2. Process each payment individually
    for rec in recent_payments:
        try:
            # Download the proof image
            file = await bot.get_file(rec['proof_file_id'])
            path = f"downloads/stress_{rec['id']}.png"
            if not os.path.exists("downloads"): os.makedirs("downloads")
            await bot.download_file(file.file_path, path)
            
            # Run Local OCR
            local = architect.extract_local_data(path)
            
            # Run API Verification if Ref found
            is_real = False
            bank_data = {}
            if local['ref']:
                bank_data = await architect.verify_external(local['ref'], local['provider'])
                is_real = bank_data.get("success", False)
            
            # Logic Check for "Hilawe" (the beneficiary)
            receiver_name = str(bank_data.get("data", {}).get("receiver", "")).upper()
            is_hilawe = "HILAWE" in local['raw_text'].upper() or "HILAWE" in receiver_name
            
            # Build Detailed Caption
            report = (
                f"📑 <b>AUDIT REPORT: ID #{rec['id']}</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🏦 <b>Bank:</b> {local['provider']}\n"
                f"🆔 <b>Ref No:</b> <code>{local['ref'] or 'NOT DETECTED'}</code>\n"
                f"💰 <b>OCR Amount:</b> {local['amount'] or '???'} ETB\n"
                f"✅ <b>Bank Verified:</b> {'YES' if is_real else 'NO'}\n"
                f"👤 <b>Target Match:</b> {'✅ HILAWE FOUND' if is_hilawe else '❌ NOT FOUND'}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🏁 <b>FINAL:</b> {'🟢 VALID' if is_real and is_hilawe else '🔴 FLAG'}"
            )

            # Send as a Photo message so the admin can see the receipt and data together
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=rec['proof_file_id'], # Use original file_id to save bandwidth
                caption=report,
                parse_mode="HTML"
            )

            # Cleanup local temp file
            if os.path.exists(path): os.remove(path)
            
        except Exception as e:
            await callback.message.answer(f"⚠️ **Error Processing ID {rec['id']}:**\n<code>{str(e)}</code>", parse_mode="HTML")

    await status_msg.delete() # Remove the "Fetching..." message when done