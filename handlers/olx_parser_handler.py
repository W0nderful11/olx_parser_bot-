import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.olx_parser import run_parser, search_run_parser, split_text
from utils.db import get_last_update_sync, get_parsed_data_sync

olx_parser_router = Router()
search_router = Router()


# FSM-состояния для выбора региона, категории, подкатегории и поиска
class ParseStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_subcategory = State()
    waiting_for_new_city = State()
    waiting_for_search_query = State()


# Полный список регионов
CITY_MAPPING = {
    "abay": "Абая",
    "akm": "Акмолинская",
    "akt": "Актюбинская",
    "alm": "Алматинская",
    "atr": "Атырауская",
    "vko": "Восточно-Казахстанская",
    "zhm": "Жамбылская",
    "zhetisu": "Жетысуская",
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
}

# Подкатегории для всех категорий. Если для категории нет списка – используется дефолтное меню {"all": "Все"}
SUBCATEGORY_MAPPING = {
    "uslugi": {
        "razvlecheniya": "Развлечения",
        "krasota_i_zdorove": "Красота и здоровье",
        "dlya_biznesa": "Для бизнеса",
        "avto_uslugi": "Автоуслуги",
        "bytovye_uslugi": "Бытовые услуги"
    },
    "stroitelstvo_remont": {"all": "Все"},
    "prokat_tovarov": {"all": "Все"},
    "nedvizhimost": {"all": "Все"},
    "elektronika": {"all": "Все"},
    "dom_i_sad": {"all": "Все"},
    "rabota": {"all": "Все"},
    "moda_i_stil": {"all": "Все"},
    "detskiy_mir": {"all": "Все"},
    "hobbi_otdyh_sport": {"all": "Все"},
    "transport": {"all": "Все"},
    "zhivotnye": {"all": "Все"},
    "otdam_darom": {"all": "Все"}
}


def build_keyboard(mapping: dict, prefix: str, buttons_per_row: int = 2) -> types.InlineKeyboardMarkup:
    buttons = []
    row = []
    for idx, (code, name) in enumerate(mapping.items(), 1):
        btn = types.InlineKeyboardButton(text=name, callback_data=f"{prefix}:{code}")
        row.append(btn)
        if idx % buttons_per_row == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def build_main_menu_keyboard(user_city: str = "Не выбран") -> types.InlineKeyboardMarkup:
    keyboard = [
        [types.InlineKeyboardButton(text="Запустить парсинг OLX", callback_data="olx_parse")],
        [types.InlineKeyboardButton(text="Поиск по названию", callback_data="search")],
        [types.InlineKeyboardButton(text="Остальное", callback_data="others")],
        [types.InlineKeyboardButton(text=f"Регион: {user_city}", callback_data="change_city")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


async def auto_delete_message(message: types.Message, delay: int = 120):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение: {e}")


# Обработка поиска по названию
@search_router.callback_query(lambda c: c.data == "search")
async def search_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название для поиска:")
    await state.set_state(ParseStates.waiting_for_search_query)
    await callback.answer()


@search_router.message(lambda message: message.text and message.text.strip() != "")
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    await message.answer(f"Поиск по запросу '{query}' запущен. Пожалуйста, подождите...")
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, search_run_parser, query)
    offers = result.strip().split("\n\n")
    groups = ["\n\n".join([grp for grp in offers[i:i + 5] if grp.strip()]) for i in range(0, len(offers), 5)]
    await state.update_data(pagination=groups, current_page=0)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    if len(groups) > 1:
        keyboard.inline_keyboard.append([types.InlineKeyboardButton(text="Далее", callback_data="next_page")])
    await message.answer("Результаты поиска:\n\n" + (groups[0] if groups else "Нет данных."), reply_markup=keyboard)
    await state.clear()


@olx_parser_router.callback_query(lambda c: c.data == "others")
async def others_menu(callback: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Изменить регион", callback_data="change_city")],
        [types.InlineKeyboardButton(text="Связаться с админом", callback_data="contact_admin")],
        [types.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    sent = await callback.message.answer("Остальное:", reply_markup=keyboard)
    asyncio.create_task(auto_delete_message(sent))
    await callback.answer()


@olx_parser_router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_city = data.get("city", "Не выбран")
    region_name = CITY_MAPPING.get(user_city, "Неизвестный регион")
    keyboard = build_main_menu_keyboard(region_name)
    await callback.message.answer("Главное меню:", reply_markup=keyboard)
    await callback.answer()


@olx_parser_router.callback_query(lambda c: c.data == "change_city")
async def change_city(callback: types.CallbackQuery, state: FSMContext):
    keyboard = build_keyboard(CITY_MAPPING, "new_city", buttons_per_row=2)
    sent = await callback.message.answer("Выберите новый регион:", reply_markup=keyboard)
    asyncio.create_task(auto_delete_message(sent))
    await state.set_state(ParseStates.waiting_for_new_city)
    await callback.answer()


@olx_parser_router.callback_query(lambda c: c.data and c.data.startswith("new_city:"), ParseStates.waiting_for_new_city)
async def new_city_selected(callback: types.CallbackQuery, state: FSMContext):
    city_code = callback.data.split(":", 1)[1]
    await state.update_data(city=city_code)
    city_name = CITY_MAPPING.get(city_code, "Неизвестный регион")
    sent = await callback.message.answer(f"Регион изменён на: {city_name}")
    asyncio.create_task(auto_delete_message(sent))
    keyboard = build_main_menu_keyboard(city_name)
    await callback.message.answer("Главное меню:", reply_markup=keyboard)
    await callback.answer()


# Запуск парсинга – сначала выбирается категория, затем подкатегория
@olx_parser_router.callback_query(lambda c: c.data == "olx_parse")
async def process_olx_parse(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "city" in data:
        user_city = data["city"]
        region_name = CITY_MAPPING.get(user_city, "Неизвестный регион")
        await callback.message.answer("Пожалуйста, подождите, данные загружаются...")
        # Если данные актуальны (младше 7 дней) – извлекаем их из базы
        if user_city in ("akm", "alm"):
            last_update = await asyncio.get_running_loop().run_in_executor(
                None, get_last_update_sync, CATEGORY_MAPPING.get(data.get("category", "uslugi"), "Услуги"), user_city
            )
            if last_update and (datetime.now() - last_update) < timedelta(days=7):
                result = await asyncio.get_running_loop().run_in_executor(
                    None, get_parsed_data_sync, CATEGORY_MAPPING.get(data.get("category", "uslugi"), "Услуги"),
                    user_city
                )
                parts = split_text(f"Данные обновлены:\n\n{result}")
                for part in parts:
                    await callback.message.answer(part)
                keyboard = build_main_menu_keyboard(region_name)
                await callback.message.answer("Главное меню:", reply_markup=keyboard)
                await callback.answer()
                return
        # Выводим меню категорий
        keyboard = build_keyboard(CATEGORY_MAPPING, "category", buttons_per_row=2)
        sent = await callback.message.answer(f"Ваш регион: {region_name}\nВыберите категорию для парсинга:",
                                             reply_markup=keyboard)
        asyncio.create_task(auto_delete_message(sent))
        await state.set_state(ParseStates.waiting_for_category)
    else:
        keyboard = build_keyboard(CITY_MAPPING, "new_city", buttons_per_row=2)
        sent = await callback.message.answer("Сначала выберите регион:", reply_markup=keyboard)
        asyncio.create_task(auto_delete_message(sent))
        await state.set_state(ParseStates.waiting_for_new_city)
    await callback.answer()


@olx_parser_router.callback_query(lambda c: c.data and c.data.startswith("category:"), ParseStates.waiting_for_category)
async def category_selected(callback: types.CallbackQuery, state: FSMContext):
    category_code = callback.data.split(":", 1)[1]
    await state.update_data(category=category_code)
    data = await state.get_data()
    city_code = data.get("city")
    region_name = CITY_MAPPING.get(city_code, "Неизвестный регион")
    selected_category = CATEGORY_MAPPING.get(category_code, "Неизвестная категория")

    # Выводим подкатегории для выбранной категории
    subcats = SUBCATEGORY_MAPPING.get(category_code, {"all": "Все"})
    subcat_keyboard = build_keyboard(subcats, "subcategory", buttons_per_row=2)
    await callback.message.answer(
        f"Вы выбрали категорию «{selected_category}». Теперь выберите подкатегорию:",
        reply_markup=subcat_keyboard
    )
    await state.set_state(ParseStates.waiting_for_subcategory)


@olx_parser_router.callback_query(lambda c: c.data and c.data.startswith("subcategory:"),
                                  ParseStates.waiting_for_subcategory)
async def subcategory_selected(callback: types.CallbackQuery, state: FSMContext):
    subcategory_code = callback.data.split(":", 1)[1]
    await state.update_data(subcategory=subcategory_code)
    data = await state.get_data()
    city_code = data.get("city")
    region_name = CITY_MAPPING.get(city_code, "Неизвестный регион")
    selected_category = CATEGORY_MAPPING.get(data.get("category", "uslugi"), "Неизвестная категория")

    await callback.message.answer(
        f"Задача запущена! Парсинг для категории «{selected_category}» (подкатегория «{subcategory_code}») в регионе «{region_name}» начат. Ожидайте результата..."
    )
    await callback.answer()
    asyncio.create_task(
        process_parsing(selected_category, data.get("category"), city_code, region_name, callback, state))


async def process_parsing(selected_category: str, category_code: str, city_code: str, region_name: str,
                          callback: types.CallbackQuery, state: FSMContext):
    loop = asyncio.get_running_loop()
    # Запуск парсинга происходит после выбора подкатегории
    result = await loop.run_in_executor(None, run_parser, category_code, city_code)
    offers = result.strip().split("\n\n")
    groups = ["\n\n".join([grp for grp in offers[i:i + 5] if grp.strip()]) for i in range(0, len(offers), 5)]
    await state.update_data(pagination=groups, current_page=0)

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    if len(groups) > 1:
        keyboard.inline_keyboard.append([types.InlineKeyboardButton(text="Далее", callback_data="next_page")])
    group0 = groups[0] if groups and groups[0].strip() else "Нет данных."
    await callback.message.answer("Парсинг завершён!\n\n" + group0, reply_markup=keyboard)


@olx_parser_router.callback_query(lambda c: c.data == "next_page")
async def next_page(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    groups = data.get("pagination", [])
    current_page = data.get("current_page", 0)
    found = False
    while current_page + 1 < len(groups):
        current_page += 1
        if groups[current_page].strip():
            found = True
            break
    if found:
        await state.update_data(current_page=current_page)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
        if current_page + 1 < len(groups):
            keyboard.inline_keyboard.append([types.InlineKeyboardButton(text="Далее", callback_data="next_page")])
        await callback.message.answer(groups[current_page], reply_markup=keyboard)
    else:
        await callback.answer("Нет больше данных.", show_alert=True)
    await callback.answer()


@olx_parser_router.callback_query(lambda c: c.data == "contact_admin")
async def contact_admin(callback: types.CallbackQuery):
    admin_contact = "Свяжитесь с администратором: @admin_username"
    sent = await callback.message.answer(admin_contact)
    asyncio.create_task(auto_delete_message(sent))
    await callback.answer()
