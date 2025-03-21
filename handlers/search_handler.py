from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

search_router = Router()

class SearchStates(StatesGroup):
    waiting_for_query = State()

@search_router.message(Command("search"))
async def search_command(message: types.Message, state: FSMContext):
    await message.answer("Введите запрос для поиска:")
    await state.set_state(SearchStates.waiting_for_query)

@search_router.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    BASE_URL = "https://www.olx.kz"
    search_url = f"{BASE_URL}/?q={query}"
    response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    soup = BeautifulSoup(response.text, 'lxml')
    results = soup.find_all("div", {"data-cy": "l-card"})
    if not results:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Вся страна", callback_data="all_country")]
        ])
        await message.answer("Ничего не найдено для вашего региона. Попробуйте поиск по всей стране.", reply_markup=keyboard)
    else:
        reply = f"Найдено {len(results)} результатов.\n\n"
        for card in results[:5]:
            try:
                title_tag = card.find("h6")
                title = title_tag.text.strip() if title_tag else "Нет заголовка"
                link_tag = card.find("a")
                link = link_tag.get("href") if link_tag else "Нет ссылки"
                if link and link.startswith("/"):
                    link = urljoin(BASE_URL, link)
                reply += f"Название: {title}\nСсылка: {link}\n\n"
            except Exception:
                continue
        await message.answer(reply)
    await state.clear()

@search_router.callback_query(lambda c: c.data == "all_country")
async def process_all_country(callback: types.CallbackQuery, state: FSMContext):
    BASE_URL = "https://www.olx.kz"
    query = "автомат"  # Можно модифицировать, чтобы использовать сохранённый запрос
    search_url = f"{BASE_URL}/list/q-{query}/"
    response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    soup = BeautifulSoup(response.text, 'lxml')
    results = soup.find_all("div", {"data-cy": "l-card"})
    reply = f"Найдено {len(results)} объявлений по запросу '{query}' по всей стране.\n\n"
    for card in results[:5]:
        try:
            title_tag = card.find("h4", {"class": "css-10ofhqw"}) or card.find("h4")
            title = title_tag.text.strip() if title_tag else "Нет заголовка"
            price_tag = card.find("h3", {"class": "css-fqcbii"}) or card.find("p", {"class": "price"})
            price = price_tag.text.strip() if price_tag else "Нет цены"
            desc_tag = card.find("div", {"class": "css-19duwlz"})
            description = desc_tag.get_text(separator="\n").strip() if desc_tag else "Нет описания"
            phone_tag = card.find("a", {"data-testid": "contact-phone", "class": "css-v1ndtc"})
            phone = phone_tag.text.strip() if phone_tag else "Нет телефона"
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
