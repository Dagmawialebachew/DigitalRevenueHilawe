# config.py
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

def env_list(key: str) -> list[int]:
    val = os.getenv(key, "")
    return [int(x.strip()) for x in val.split(",") if x.strip()]

@dataclass(frozen=True)
class Settings:
    # Core Bot Settings
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = field(default_factory=lambda: env_list("ADMIN_IDS"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "") # PostgreSQL DSN
    
    # Business Logic
    # BANK_DETAILS: str = os.getenv("BANK_DETAILS", "CBE: 1000... | Telebirr: 09...")
    
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "")
    PORT: int = int(os.getenv("PORT", "8080"))
    
    # Admin Channel Logging
    ADMIN_PAYMENT_LOG_ID: int = int(os.getenv("ADMIN_PAYMENT_LOG_ID", "0"))
    ADMIN_ERROR_LOG_ID: int = int(os.getenv("ADMIN_ERROR_LOG_ID", "0"))
    ADMIN_NEW_USER_LOG_ID: int = int(os.getenv("ADMIN_NEW_USER_LOG_ID", "0"))
    ADMIN_SCHEDULER_LOG_ID: int = int(os.getenv("ADMIN_SCHEDULER_LOG_ID", "0"))
    

    BANK_CBE = os.getenv("BANK_CBE", "")
    BANK_CBE_NAME = os.getenv("BANK_CBE_NAME", "")

    BANK_BOA = os.getenv("BANK_BOA", "")
    BANK_BOA_NAME = os.getenv("BANK_BOA_NAME", "")

    BANK_TELEBIRR = os.getenv("BANK_TELEBIRR", "")
    BANK_TELEBIRR_NAME = os.getenv("BANK_TELEBIRR_NAME", "")
    
    
    BROADCAST_BATCH_SLEEP: float = float(os.getenv("BROADCAST_BATCH_SLEEP", "0.06"))
    BROADCAST_DEAL_PRICE: float = float(os.getenv("BROADCAST_DEAL_PRICE", "399"))
    BROADCAST_DURATION_HOURS: int = int(os.getenv("BROADCAST_DURATION_HOURS", "30"))
    REMINDER_INTERVAL_SECONDS: int = int(os.getenv("REMINDER_INTERVAL_SECONDS", "900"))
    DESIGN_PHOTO_ID: str = os.getenv("DESIGN_PHOTO_ID", "AgACAgQAAxkBAAICD2ml995Hk2v_RvtWWalCMmnL_HVbAAJ_Dmsbkw8xUTFX3jgeoXQOAQADAgADdwADOgQ")


settings = Settings()

# Ensure required directories exist for local caching if needed
Path("./logs").mkdir(parents=True, exist_ok=True)