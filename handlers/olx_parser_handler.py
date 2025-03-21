import asyncio
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.state import StateFilter
from utils.selenium_parser import run_selenium_parser, split_text
from config.subcategories import SUBCATEGORY_MAPPING_FULL
from handlers.start_handler import build_main_menu

olx_parser_router = Router()

class ParseStates(StatesGroup):
    waiting_for_region = State()
    waiting_for_category = State()
    waiting_for_subcategory = State()

REGION_MAPPING = {
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
}

CATEGORY_MAPPING = {
    "nedvizhimost": "Недвижимость",
    "uslugi": "Услуги",
    "stroitelstvo-remont": "Строительство и ремонт",
    "prokat-tovarov": "Аренда и прокат товаров",
    "elektronika": "Электроника",
    "dom-i-sad": "Дом и сад",
    "rabota": "Работа",
    "moda-i-stil": "Мода и стиль",
    "detskiy-mir": "Детский мир",
    "hobbi-otdyh-sport": "Хобби, отдых и спорт"
}

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
        if ad["Фото"] and ad["Фото"].strip() and ad["Фото"].startswith("http"):
            await message.answer_photo(photo=ad["Фото"], caption=text)
        else:
            await message.answer(text)
    current_index += len(batch)
    await state.update_data(current_index=current_index)
    if current_index < len(ads):
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Продолжить", callback_data="next_ads")]
        ])
        await message.answer("Нажмите 'Продолжить' для следующих объявлений", reply_markup=keyboard)
    else:
        await message.answer("Все объявления отправлены.")
        user_region = REGION_MAPPING.get((await state.get_data()).get("region"), "Не выбран")
        keyboard = build_main_menu(user_region)
        await message.answer("Главное меню:", reply_markup=keyboard)

@olx_parser_router.callback_query(lambda c: c.data == "olx_parse")
async def start_parsing(callback: types.CallbackQuery, state: FSMContext):
    print("Кнопка 'Запустить парсинг OLX' нажата!")  # Отладочное сообщение
    try:
        await callback.answer()
    except Exception:
        pass
    # Очищаем состояние, чтобы не использовать старые данные
    await state.clear()
    # Запрашиваем выбор региона
    keyboard = build_inline_keyboard(REGION_MAPPING, "region", buttons_per_row=2)
    await callback.message.answer("Выберите регион:", reply_markup=keyboard)
    await state.set_state(ParseStates.waiting_for_region)

@olx_parser_router.callback_query(lambda c: c.data.startswith("region:"), StateFilter(ParseStates.waiting_for_region))
async def region_chosen(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    region_code = callback.data.split(":")[1]
    region_name = REGION_MAPPING.get(region_code, "Неизвестный регион")
    await state.update_data(region=region_code)
    await callback.message.answer(f"Регион выбран: {region_name}")
    keyboard = build_inline_keyboard(CATEGORY_MAPPING, "category", buttons_per_row=2)
    await callback.message.answer("Выберите категорию:", reply_markup=keyboard)
    await state.set_state(ParseStates.waiting_for_category)

@olx_parser_router.callback_query(lambda c: c.data.startswith("category:"), StateFilter(ParseStates.waiting_for_category))
async def category_chosen(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    category_code = callback.data.split(":")[1]
    category_name = CATEGORY_MAPPING.get(category_code, "Неизвестная категория")
    await state.update_data(category=category_code)
    subcats = SUBCATEGORY_MAPPING_FULL.get(category_code)
    if subcats:
        keyboard = build_inline_keyboard(subcats, "subcategory", buttons_per_row=2)
        await callback.message.answer(f"Вы выбрали категорию «{category_name}». Выберите подкатегорию:", reply_markup=keyboard)
        await state.set_state(ParseStates.waiting_for_subcategory)
    else:
        await state.update_data(subcategory="all")
        await callback.message.answer(f"Запускается парсинг для категории «{category_name}». Ожидайте...")
        data = await state.get_data()
        region_code = data.get("region")
        result_text, ads_all = await asyncio.get_running_loop().run_in_executor(
            None, run_selenium_parser, category_code, region_code, "all"
        )
        await state.update_data(ads=ads_all, current_index=0)
        await send_ads_batch(callback.message, state)
        user_region = REGION_MAPPING.get(region_code, "Не выбран")
        keyboard = build_main_menu(user_region)
        await callback.message.answer("Главное меню:", reply_markup=keyboard)
        await state.clear()

@olx_parser_router.callback_query(lambda c: c.data.startswith("subcategory:"), StateFilter(ParseStates.waiting_for_subcategory))
async def subcategory_chosen(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    subcategory_code = callback.data.split(":")[1]
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
    try:
        await callback.answer()
    except Exception:
        pass

@olx_parser_router.callback_query(lambda c: c.data == "change_region")
async def change_region(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    keyboard = build_inline_keyboard(REGION_MAPPING, "region", buttons_per_row=2)
    await callback.message.answer("Выберите новый регион:", reply_markup=keyboard)
    await state.set_state(ParseStates.waiting_for_region)

@olx_parser_router.callback_query(lambda c: c.data == "others")
async def others_menu(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Изменить регион", callback_data="change_region")],
        [types.InlineKeyboardButton(text="Связаться с админом", callback_data="contact_admin")],
        [types.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    await callback.message.answer("Остальное:", reply_markup=keyboard)

@olx_parser_router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    data = await state.get_data()
    region_code = data.get("region", None)
    user_region = REGION_MAPPING.get(region_code, "Не выбран")
    keyboard = build_main_menu(user_region)
    await callback.message.answer("Главное меню:", reply_markup=keyboard)
    await state.clear()

@olx_parser_router.callback_query(lambda c: c.data == "contact_admin")
async def contact_admin(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
    admin_contact = "Свяжитесь с администратором: @mikoto699"
    await callback.message.answer(admin_contact)
