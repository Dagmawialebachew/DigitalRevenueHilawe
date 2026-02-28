import time
import asyncio
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, message_interval: float = 0.8, callback_interval: float = 0.4) -> None:
        super().__init__()
        self.message_interval = message_interval
        self.callback_interval = callback_interval
        
        # We store (timestamp)
        self.users: dict[str, float] = {}
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user or user.is_bot:
            return await handler(event, data)

        user_id = user.id
        now = time.time()
        
        # Determine event type and threshold
        is_callback = isinstance(event, CallbackQuery)
        event_key = f"{'cb' if is_callback else 'msg'}_{user_id}"
        limit = self.callback_interval if is_callback else self.message_interval

        # Check Throttle
        last_time = self.users.get(event_key, 0.0)
        if (now - last_time) < limit:
            if is_callback:
                # Get language from data (provided by your LanguageMiddleware)
                lang = data.get("language", "EN")
                alert = "⚡️ Easy, Champion!" if lang == "EN" else "⚡️ ቀስ ይበሉ፣ ሻምፒዮን!"
                try:
                    await event.answer(alert, show_alert=False)
                except Exception:
                    pass
            return None # Drop event

        # Update last seen
        self.users[event_key] = now
        
        # Periodic Cleanup (Every 1000 requests, clear users older than 10 seconds)
        # This prevents the memory leak
        if len(self.users) > 1000:
            self._prune_old_users(now)

        return await handler(event, data)

    def _prune_old_users(self, now: float):
        """Removes users from cache who haven't messaged in a while."""
        threshold = 10.0 # Anyone older than 10 seconds is irrelevant to throttling
        self.users = {k: v for k, v in self.users.items() if (now - v) < threshold}