import os
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import requests
from utils.ids_gather import gather_data
from utils.crawler import Crawler
from utils.db import insert_offers_sync

BASE_URL = "https://www.olx.kz"


def run_parser(category_code, city_code, subcategory_code=None):
    """
    Основной синхронный парсер для OLX.kz по выбранной категории (и подкатегории, если передана).
    Сначала собираются ссылки (с параметром limit=5 для тестирования), затем с помощью Crawler извлекаются подробные данные,
    данные сохраняются в базу данных и возвращается итоговый текст для Telegram со структурированными объявлениями.
    """
    # Преобразуем код категории для URL (замена "_" на "-")
    category_url_code = category_code.replace("_", "-")

    # Собираем ссылки; функция gather_data учитывает переданный limit
    links = gather_data(city_code, category_url_code, limit=5)

    # Извлекаем подробные данные по объявлениям
    crawler = Crawler(category_url_code, city_code)
    offers = crawler.get_data()  # Ожидается список словарей с ключами: id, name, price, description, phone, url

    # Сохраняем данные в БД (если настроено)
    insert_offers_sync(offers, category_code, city_code)

    # Формируем итоговый текст с объявлениями
    result_text = f"Найдено {len(offers)} объявлений.\n\n"
    for offer in offers:
        result_text += (
            f"Название: {offer.get('name', 'Нет заголовка')}\n"
            f"Цена: {offer.get('price', 'Нет цены')}\n"
            f"Описание: {offer.get('description', 'Нет описания')}\n"
            f"Телефон: {offer.get('phone', 'Нет телефона')}\n"
            f"Ссылка: {offer.get('url', 'Нет ссылки')}\n\n"
        )
    return result_text


async def fetch_page(session, url, semaphore):
    """
    Асинхронно загружает страницу по URL, используя semaphore для ограничения одновременных запросов.
    """
    async with semaphore:
        async with session.get(url, timeout=10) as response:
            return await response.text()


async def parse_ads_from_page(page_html):
    """
    Извлекает объявления со страницы, используя BeautifulSoup.
    """
    soup = BeautifulSoup(page_html, 'lxml')
    ads = []
    cards = soup.find_all("div", {"data-cy": "l-card"})
    for card in cards:
        title_tag = card.find("h4", {"class": "css-10ofhqw"}) or card.find("h4")
        title = title_tag.get_text(strip=True) if title_tag else "Нет заголовка"
        price_tag = card.find("h3", {"class": "css-fqcbii"}) or card.find("p", {"class": "price"})
        price = price_tag.get_text(strip=True) if price_tag else "Нет цены"
        desc_tag = card.find("div", {"class": "css-19duwlz"})
        description = desc_tag.get_text(separator="\n", strip=True) if desc_tag else "Нет описания"
        phone_tag = card.find("a", {"data-testid": "contact-phone", "class": "css-v1ndtc"})
        phone = phone_tag.get_text(strip=True) if phone_tag else "Нет телефона"
        link_tag = card.find("a", href=True)
        link = link_tag["href"] if link_tag else "Нет ссылки"
        if link.startswith("/"):
            link = urljoin(BASE_URL, link)
        ads.append({
            "Название": title,
            "Цена": price,
            "Описание": description,
            "Телефон": phone,
            "Ссылка": link
        })
    return ads


async def async_run_parser(category_code, region_code, subcategory_code):
    """
    Асинхронный парсер для OLX.kz по выбранной категории, региону и подкатегории.
    Формирует URL вида:
      https://www.olx.kz/<category_code>/<region_code>/<subcategory_code>/
    Загружает страницы параллельно (до 5 одновременно) и возвращает итоговый текст и список объявлений.

    Для тестирования число страниц ограничено до 5.
    """
    # Формируем URL для выбранной подкатегории
    url = f"{BASE_URL}/{category_code}/{region_code}/{subcategory_code}/"
    semaphore = asyncio.Semaphore(5)
    async with aiohttp.ClientSession() as session:
        first_page_html = await fetch_page(session, url, semaphore)
        soup = BeautifulSoup(first_page_html, 'lxml')
        try:
            pagination_items = soup.find_all('li', {'data-testid': 'pagination-list-item'})
            if pagination_items:
                total_pages = int(pagination_items[-1].get_text(strip=True))
            else:
                total_pages = 1
        except Exception:
            total_pages = 1

        # Для тестирования ограничим число страниц до 5
        total_pages = min(total_pages, 5)
        tasks = []
        for page in range(1, total_pages + 1):
            page_url = f"{url}?page={page}"
            tasks.append(fetch_page(session, page_url, semaphore))
        pages_html = await asyncio.gather(*tasks, return_exceptions=True)

    ads_all = []
    for page_html in pages_html:
        if isinstance(page_html, Exception):
            continue
        ads = await parse_ads_from_page(page_html)
        ads_all.extend(ads)

    result_text = f"Найдено {len(ads_all)} объявлений.\n\n"
    for ad in ads_all:
        result_text += (
            f"Название: {ad['Название']}\n"
            f"Цена: {ad['Цена']}\n"
            f"Описание: {ad['Описание']}\n"
            f"Телефон: {ad['Телефон']}\n"
            f"Ссылка: {ad['Ссылка']}\n\n"
        )
    return result_text, ads_all


def search_run_parser(query):
    """
    Парсит результаты поиска по названию.
    Формирует URL вида:
      https://www.olx.kz/list/q-<query>/
    Собирает первые 20 объявлений, извлекая:
      - Название из <h4 class="css-10ofhqw">,
      - Цена из <h3 class="css-fqcbii">,
      - Описание из <div class="css-19duwlz">,
      - Телефон из <a data-testid="contact-phone" class="css-v1ndtc">,
      - Ссылку из тега <a>.

    Результат возвращается в виде строки, где каждое объявление структурировано.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15'
    }
    query_encoded = quote(query)
    search_url = f"{BASE_URL}/list/q-{query_encoded}/"
    response = requests.get(search_url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'lxml')
    cards = soup.find_all("div", {"data-cy": "l-card"})

    result_text = f"Найдено {len(cards)} объявлений по запросу '{query}'.\n\n"
    for card in cards[:20]:
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
        result_text += (
            f"Название: {title}\n"
            f"Цена: {price}\n"
            f"Описание: {description}\n"
            f"Телефон: {phone}\n"
            f"Ссылка: {link}\n\n"
        )
    return result_text


def split_text(text: str, max_length: int = 4096) -> list:
    """
    Разбивает длинный текст на части, чтобы каждая часть не превышала max_length символов.
    Это нужно для отправки сообщений в Telegram.
    """
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]
