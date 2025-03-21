import asyncio
import logging
from utils.olx_parser import run_parser
from utils.db import get_last_update_sync

async def delete_old_offers():
    import asyncpg
    import os
    from dotenv import load_dotenv
    load_dotenv()
    POSTGRES_URI = os.getenv("POSTGRES_URI")
    if not POSTGRES_URI:
        logging.error("POSTGRES_URI не задан в .env")
        return
    try:
        conn = await asyncpg.connect(POSTGRES_URI)
        await conn.execute("DELETE FROM olx_data WHERE created < NOW() - INTERVAL '7 days'")
        await conn.close()
        logging.info("Старые данные удалены")
    except Exception as e:
        logging.error(f"Ошибка при удалении старых данных: {e}")

# Используем все регионы и категории
IMPORTANT_REGIONS = list({
    "abay": "Абая",
    "akm": "Акмолинская",
    "akt": "Актюбинская",
    "alm": "Алматинская",
    "atr": "Атырауская",
    "vko": "Восточно-Казахстанская",
    "zhm": "Жамбылская",
    "zhetisu": "Жетысусская",
    "zko": "Западно-Казахстанская",
    "kar": "Карагандинская",
    "kus": "Костанайская",
    "kyz": "Кызылординская",
    "man": "Мангистауская",
    "pav": "Павлодарская",
    "sko": "Северо-Казахстанская",
    "uko": "Туркестанская",
    "ulytau": "Улытауская"
}.keys())

CATEGORIES = list({
    "uslugi": "Услуги",
    "stroitelstvo_remont": "Строительство и ремонт",
    "prokat_tovarov": "Аренда и прокат товаров",
    "nedvizhimost": "Недвижимость",
    "elektronika": "Электроника",
    "dom_i_sad": "Дом и сад",
    "rabota": "Работа",
    "moda_i_stil": "Мода и стиль",
    "detskiy_mir": "Детский мир",
    "hobbi_otdyh_sport": "Хобби, отдых и спорт",
    "transport": "Транспорт",
    "zhivotnye": "Животные",
    "otdam_darom": "Отдам даром"
}.keys())

async def auto_update():
    while True:
        logging.info("Auto-update task started")
        await delete_old_offers()
        for region in IMPORTANT_REGIONS:
            for category in CATEGORIES:
                logging.info(f"Автообновление для категории {category} в регионе {region}")
                result = run_parser(category, region)
                logging.info(f"Обновление завершено для {category} в регионе {region}")
        logging.info("Auto-update task completed. Сплю 7 дней...")
        await asyncio.sleep(7 * 24 * 3600)
