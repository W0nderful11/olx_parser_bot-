import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

BASE_URL = "https://www.olx.kz"

async def fetch_page(session, url, semaphore):
    async with semaphore:
        async with session.get(url, timeout=10) as response:
            return await response.text()

async def parse_ads_from_page(page_html):
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

async def async_parse_ads(url, limit_pages=5):
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

        total_pages = min(total_pages, limit_pages)
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

async def async_search_run_parser(query):
    query_encoded = quote(query)
    url = f"{BASE_URL}/list/q-{query_encoded}/"
    return await async_parse_ads(url)

async def async_run_parser(category_code, region_code, subcategory_code):
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

def split_text(text: str, max_length: int = 4096) -> list:
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]
