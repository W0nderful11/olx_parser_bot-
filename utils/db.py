import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

def insert_offers_sync(offers, category, city):
    asyncio.run(_insert_offers(offers, category, city))

async def _insert_offers(offers, category, city):
    POSTGRES_URI = os.getenv("POSTGRES_URI")
    conn = await asyncpg.connect(POSTGRES_URI)
    for offer in offers:
        await conn.execute("""
            INSERT INTO olx_data (external_id, title, price, url, phone, description, category)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (external_id) DO NOTHING;
        """, offer.get('id', ''), offer.get('name', ''), offer.get('price', ''),
           offer.get('url', ''), offer.get('phone', ''), offer.get('description', ''), category)
    await conn.close()

def get_last_update_sync(category, city):
    async def _get():
        POSTGRES_URI = os.getenv("POSTGRES_URI")
        conn = await asyncpg.connect(POSTGRES_URI)
        row = await conn.fetchrow("""
            SELECT MAX(created) as last_update FROM olx_data
            WHERE category = $1
        """, category)
        await conn.close()
        return row['last_update'] if row and row['last_update'] else None
    return asyncio.run(_get())

def get_parsed_data_sync(category, city):
    async def _get():
        POSTGRES_URI = os.getenv("POSTGRES_URI")
        conn = await asyncpg.connect(POSTGRES_URI)
        rows = await conn.fetch("""
            SELECT title, price, url, phone, description FROM olx_data
            WHERE category = $1 ORDER BY created DESC
        """, category)
        await conn.close()
        result = ""
        for row in rows:
            result += (f"Название: {row['title']}\nЦена: {row['price']}\nОписание: {row['description']}\n"
                       f"Телефон: {row['phone']}\nСсылка: {row['url']}\n\n")
        return result
    return asyncio.run(_get())
