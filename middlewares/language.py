# language.py
# middlewares/language.py
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable

class LanguageMiddleware(BaseMiddleware):
    def __init__(self, db):
        super().__init__()
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Inject db into handler data
        data["db"] = self.db

        # Example: fetch language preference from DB
        user = data.get("event_from_user")
        if user:
            lang = await self.db.get_user_language(user.id)
            data["lang"] = lang or "EN"

        return await handler(event, data)
