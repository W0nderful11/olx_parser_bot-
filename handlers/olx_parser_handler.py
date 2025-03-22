import asyncio
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.selenium_parser import run_selenium_parser, run_selenium_search_parser, split_text
from handlers.start_handler import build_main_menu

olx_parser_router = Router()

# FSM-состояния для выбора региона, категории, подкатегории и поиска
class ParseStates(StatesGroup):
    waiting_for_region = State()
    waiting_for_category = State()
    waiting_for_subcategory = State()
    waiting_for_search_query = State()

# Словари регионов и категорий
REGION_MAPPING = {
    "abay": "Абая",
    "akm": "Акмолинская",
    "akt": "Актюбинская",
    "alm": "Алматинская",
    "atr": "Атырауская",
    "vko": "Восточно‑Казахстанская",
    "zhm": "Жамбылская",
    "zhetisu": "Жетысуская",
    "zko": "Западно‑Казахстанская",
    "kar": "Карагандинская",
    "kus": "Костанайская",
    "kyz": "Кызылординская",
    "man": "Мангистауская",
    "pav": "Павлодарская",
    "sko": "Северо‑Казахстанская",
    "uko": "Туркестанская",
    "ulytau": "Улытауская"
}

CATEGORY_MAPPING = {
    "nedvizhimost": "Недвижимость",
    "uslugi": "Услуги",
    "stroitelstvo_remont": "Строительство и ремонт",
    "prokat_tovarov": "Аренда и прокат товаров",
    "elektronika": "Электроника",
    "dom_i_sad": "Дом и сад",
    "rabota": "Работа",
    "moda_i_stil": "Мода и стиль",
    "detskiy_mir": "Детский мир",
    "hobbi_otdyh_sport": "Хобби, отдых и спорт"
}

# Импорт полного словаря подкатегорий
from config.subcategories import SUBCATEGORY_MAPPING_FULL

def build_inline_keyboard(options: dict, prefix: str, buttons_per_row: int = 2) -> types.InlineKeyboardMarkup:
    keyboard = []
    row = []
    for idx, (code, name) in enumerate(options.items(), start=1):
        button = types.InlineKeyboardButton(text=name, callback_data=f"{prefix}:{code}")
        row.append(button)
        if idx % buttons_per_row == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

async def send_ads_batch(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ads = data.get("ads", [])
    current_index = data.get("current_index", 0)
    batch = ads[current_index:current_index+5]
    for ad in batch:
        text = (
            f"Название: {ad['Название']}\n"
            f"Цена: {ad['Цена']}\n"
            f"Описание: {ad['Описание']}\n"
            f"Телефон: {ad['Телефон']}\n"
            f"Ссылка: {ad['Ссылка']}"
        )
        if ad.get("Фото") and ad["Фото"].strip() and ad["Фото"].startswith("http"):
            await message.answer_photo(photo=ad["Фото"], caption=text)
        else:
            await message.answer(text)
    current_index += len(batch)
    await state.update_data(current_index=current_index)
    if current_index < len(ads):
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Далее", callback_data="next_ads")]
        ])
        await message.answer("Нажмите 'Далее' для следующих объявлений", reply_markup=keyboard)
    else:
        await message.answer("Все объявления отправлены.")
        user_region = REGION_MAPPING.get((await state.get_data()).get("region"), "Не выбран")
        keyboard = build_main_menu(user_region)
        await message.answer("Главное меню:", reply_markup=keyboard)

# ОБРАБОТКА ВЫБОРА РЕГИОНА, КАТЕГОРИИ И ПОДКАТЕГОРИИ

@olx_parser_router.callback_query(lambda c: c.data == "olx_parse")
async def start_parsing(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    if "region" not in data:
        keyboard = build_inline_keyboard(REGION_MAPPING, "region", buttons_per_row=2)
        await callback.message.answer("Выберите регион:", reply_markup=keyboard)
        await state.set_state(ParseStates.waiting_for_region)
    else:
        keyboard = build_inline_keyboard(CATEGORY_MAPPING, "category", buttons_per_row=2)
        await callback.message.answer("Выберите категорию:", reply_markup=keyboard)
        await state.set_state(ParseStates.waiting_for_category)

@olx_parser_router.callback_query(lambda c: c.data.startswith("region:"), ParseStates.waiting_for_region)
async def region_chosen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    region_code = callback.data.split(":")[1]
    region_name = REGION_MAPPING.get(region_code, "Неизвестный регион")
    await state.update_data(region=region_code)
    await callback.message.answer(f"Регион выбран: {region_name}")
    keyboard = build_inline_keyboard(CATEGORY_MAPPING, "category", buttons_per_row=2)
    await callback.message.answer("Выберите категорию:", reply_markup=keyboard)
    await state.set_state(ParseStates.waiting_for_category)

@olx_parser_router.callback_query(lambda c: c.data.startswith("category:"), ParseStates.waiting_for_category)
async def category_chosen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    category_code = callback.data.split(":", 1)[1]
    category_name = CATEGORY_MAPPING.get(category_code, "Неизвестная категория")
    await state.update_data(category=category_code)
    subcats = SUBCATEGORY_MAPPING_FULL.get(category_code)
    if subcats:
        keyboard = build_inline_keyboard(subcats, "subcategory", buttons_per_row=2)
        await callback.message.answer(
            f"Вы выбрали категорию «{category_name}». Теперь выберите подкатегорию:",
            reply_markup=keyboard
        )
        await state.set_state(ParseStates.waiting_for_subcategory)
    else:
        await state.update_data(subcategory="all")
        await callback.message.answer(f"Запускается парсинг для категории «{category_name}». Ожидайте...")
        data = await state.get_data()
        region_code = data.get("region")
        # Если подкатегория равна "all", формируем URL без сегмента "all"
        result_text, ads_all = await asyncio.get_running_loop().run_in_executor(
            None, run_selenium_parser, category_code, region_code, "all"
        )
        await state.update_data(ads=ads_all, current_index=0)
        await send_ads_batch(callback.message, state)
        user_region = REGION_MAPPING.get(region_code, "Не выбран")
        keyboard = build_main_menu(user_region)
        await callback.message.answer("Главное меню:", reply_markup=keyboard)
        await state.clear()

@olx_parser_router.callback_query(lambda c: c.data.startswith("subcategory:"), ParseStates.waiting_for_subcategory)
async def subcategory_chosen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    subcategory_code = callback.data.split(":", 1)[1]
    await state.update_data(subcategory=subcategory_code)
    data = await state.get_data()
    category_code = data.get("category")
    region_code = data.get("region")
    category_name = CATEGORY_MAPPING.get(category_code, "Неизвестная категория")
    region_name = REGION_MAPPING.get(region_code, "Неизвестный регион")
    subcat_name = SUBCATEGORY_MAPPING_FULL.get(category_code, {}).get(subcategory_code, "Все")
    await callback.message.answer(
        f"Запускается парсинг для категории «{category_name}» (подкатегория «{subcat_name}») в регионе «{region_name}». Ожидайте..."
    )
    result_text, ads_all = await asyncio.get_running_loop().run_in_executor(
        None, run_selenium_parser, category_code, region_code, subcategory_code
    )
    await state.update_data(ads=ads_all, current_index=0)
    await send_ads_batch(callback.message, state)
    keyboard = build_main_menu(region_name)
    await callback.message.answer("Главное меню:", reply_markup=keyboard)
    await state.clear()

@olx_parser_router.callback_query(lambda c: c.data == "next_ads")
async def next_ads(callback: types.CallbackQuery, state: FSMContext):
    await send_ads_batch(callback.message, state)
    await callback.answer()

@olx_parser_router.callback_query(lambda c: c.data == "change_region")
async def change_region(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    keyboard = build_inline_keyboard(REGION_MAPPING, "region", buttons_per_row=2)
    await callback.message.answer("Выберите новый регион:", reply_markup=keyboard)
    await state.set_state(ParseStates.waiting_for_region)

@olx_parser_router.callback_query(lambda c: c.data == "others")
async def others_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Изменить регион", callback_data="change_region")],
        [types.InlineKeyboardButton(text="Связаться с администратором", callback_data="contact_admin")],
        [types.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    await callback.message.answer("Остальное:", reply_markup=keyboard)

@olx_parser_router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    region_code = data.get("region", None)
    user_region = REGION_MAPPING.get(region_code, "Не выбран")
    keyboard = build_main_menu(user_region)
    await callback.message.answer("Главное меню:", reply_markup=keyboard)
    await state.clear()

@olx_parser_router.callback_query(lambda c: c.data == "contact_admin")
async def contact_admin(callback: types.CallbackQuery):
    await callback.answer()
    admin_contact = "Свяжитесь с администратором: @mikoto699"
    await callback.message.answer(admin_contact)

# ============================
# ОБРАБОТКА ПОИСКА (ИНТЕГРИРОВАНА В ТОМ ЖЕ ФАЙЛЕ)
# ============================
@olx_parser_router.callback_query(lambda c: c.data == "search")
async def search_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название для поиска:")
    await state.set_state(ParseStates.waiting_for_search_query)
    await callback.answer()

@olx_parser_router.message(lambda message: message.text and message.text.strip() != "")
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    await message.answer(f"Поиск по запросу '{query}' запущен. Пожалуйста, подождите...")
    loop = asyncio.get_running_loop()
    # Используем run_selenium_search_parser для поиска по названию; функция возвращает кортеж (result_text, ads_all)
    result = await loop.run_in_executor(None, run_selenium_search_parser, query)
    if isinstance(result, tuple):
        result_text, ads_all = result
    else:
        result_text = result
        ads_all = []
    # Для поиска отправляем каждое объявление отдельно (порциями по 5)
    if ads_all:
        current_index = 0
        batch = ads_all[current_index:current_index+5]
        for ad in batch:
            text = (
                f"Название: {ad['Название']}\n"
                f"Цена: {ad['Цена']}\n"
                f"Описание: {ad['Описание']}\n"
                f"Телефон: {ad['Телефон']}\n"
                f"Ссылка: {ad['Ссылка']}"
            )
            if ad.get("Фото") and ad["Фото"].strip() and ad["Фото"].startswith("http"):
                await message.answer_photo(photo=ad["Фото"], caption=text)
            else:
                await message.answer(text)
        current_index += len(batch)
        await state.update_data(ads=ads_all, current_index=current_index)
        if current_index < len(ads_all):
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Далее", callback_data="next_search_ads")]
            ])
            await message.answer("Нажмите 'Далее' для следующих объявлений", reply_markup=keyboard)
        else:
            keyboard = build_main_menu("Не выбран")
            await message.answer("Все объявления отправлены.\nГлавное меню:", reply_markup=keyboard)
    else:
        parts = split_text(result_text)
        for part in parts:
            await message.answer(part)
    await state.clear()

@olx_parser_router.callback_query(lambda c: c.data == "next_search_ads")
async def next_search_ads(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ads_all = data.get("ads", [])
    current_index = data.get("current_index", 0)
    batch = ads_all[current_index:current_index+5]
    for ad in batch:
        text = (
            f"Название: {ad['Название']}\n"
            f"Цена: {ad['Цена']}\n"
            f"Описание: {ad['Описание']}\n"
            f"Телефон: {ad['Телефон']}\n"
            f"Ссылка: {ad['Ссылка']}"
        )
        if ad.get("Фото") and ad["Фото"].strip() and ad["Фото"].startswith("http"):
            await callback.message.answer_photo(photo=ad["Фото"], caption=text)
        else:
            await callback.message.answer(text)
    current_index += len(batch)
    await state.update_data(current_index=current_index)
    if current_index < len(ads_all):
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Далее", callback_data="next_search_ads")]
        ])
        await callback.message.answer("Нажмите 'Далее' для следующих объявлений", reply_markup=keyboard)
    else:
        keyboard = build_main_menu("Не выбран")
        await callback.message.answer("Все объявления отправлены.\nГлавное меню:", reply_markup=keyboard)
    await callback.answer()

@olx_parser_router.callback_query(lambda c: c.data == "all_country")
async def process_all_country(callback: types.CallbackQuery, state: FSMContext):
    BASE_URL = "https://www.olx.kz"
    query = "автомат"  # Здесь можно использовать сохранённый запрос, если требуется
    search_url = f"{BASE_URL}/list/q-{query}/"
    response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'lxml')
    results = soup.find_all("div", {"data-cy": "l-card"})
    reply = f"Найдено {len(results)} объявлений по запросу '{query}' по всей стране.\n\n"
    for card in results[:5]:
        try:
            title_tag = card.find("h4", {"class": "css-10ofhqw"}) or card.find("h4")
            title = title_tag.get_text(strip=True) if title_tag else "Нет заголовка"
            price_tag = card.find("h3", {"class": "css-fqcbii"}) or card.find("p", {"class": "price"})
            price = price_tag.get_text(strip=True) if price_tag else "Нет цены"
            desc_tag = card.find("div", {"class": "css-19duwlz"})
            description = desc_tag.get_text(separator="\n").strip() if desc_tag else "Нет описания"
            phone_tag = card.find("a", {"data-testid": "contact-phone", "class": "css-v1ndtc"})
            phone = phone_tag.get_text(strip=True) if phone_tag else "Нет телефона"
            link_tag = card.find("a")
            link = link_tag.get("href") if link_tag else "Нет ссылки"
            if link and link.startswith("/"):
                link = urljoin(BASE_URL, link)
            reply += (
                f"Название: {title}\nЦена: {price}\nОписание: {description}\n"
                f"Телефон: {phone}\nСсылка: {link}\n\n"
            )
        except Exception:
            continue
    await callback.message.answer(reply)
    await callback.answer()
