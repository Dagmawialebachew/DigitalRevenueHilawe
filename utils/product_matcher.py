# product_matcher.py
from database.db import Database

class ProductMatcher:
    def __init__(self, db: Database):
        self.db = db

    async def get_plan_for_user(self, user_record: dict):
        return await self.db.match_product(
            language=user_record['language'],
            level=user_record['level'],
            frequency=user_record['frequency']
        )
