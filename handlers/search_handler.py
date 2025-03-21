import asyncio
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.selenium_parser import run_selenium_search_parser, split_text
from handlers.start_handler import build_main_menu

search_router = Router()

class SearchStates(StatesGroup):
    waiting_for_search_query = State()

def build_search_menu() -> types.InlineKeyboardMarkup:
    keyboard = [
        [types.InlineKeyboardButton(text="Поиск по названию", callback_data="search")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

async def send_search_ads_batch(message: types.Message, state: FSMContext):
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
            [types.InlineKeyboardButton(text="Продолжить", callback_data="next_search_ads")]
        ])
        await message.answer("Нажмите 'Продолжить' для следующих объявлений", reply_markup=keyboard)
    else:
        await message.answer("Все объявления отправлены.")
        keyboard = build_main_menu("Не выбран")
        await message.answer("Главное меню:", reply_markup=keyboard)

@search_router.callback_query(lambda c: c.data == "search")
async def search_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Введите название для поиска:")
    await state.set_state(SearchStates.waiting_for_search_query)

@search_router.message(SearchStates.waiting_for_search_query)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    await message.answer(f"Поиск по запросу '{query}' запущен. Пожалуйста, подождите...")
    result_text, ads_all = await asyncio.get_running_loop().run_in_executor(
        None, run_selenium_search_parser, query
    )
    await state.update_data(ads=ads_all, current_index=0)
    await send_search_ads_batch(message, state)
    await state.clear()

@search_router.callback_query(lambda c: c.data == "next_search_ads")
async def next_search_ads(callback: types.CallbackQuery, state: FSMContext):
    await send_search_ads_batch(callback.message, state)
    await callback.answer()
