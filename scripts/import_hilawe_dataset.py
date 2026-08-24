from __future__ import annotations

import asyncio
import os

import asyncpg

from meal_plan.dataset_import import import_hilawe_dataset
from meal_plan.generation.dataset import load_dataset


async def main() -> None:
    url=os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required. This script never contains database credentials itself.")
    ds=load_dataset()
    pool=await asyncpg.create_pool(url,min_size=1,max_size=2)
    try:
        counts=await import_hilawe_dataset(pool,ds)
        print(f"Imported {ds.version}: {counts}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
