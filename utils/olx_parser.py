# utils/olx_parser.py
# -*- coding: utf8 -*-

import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from html import unescape
from urllib.parse import urljoin
from config.category_urls import CATEGORY_URLS

# Основной URL сайта OLX.kz
BASE_URL = "https://www.olx.kz"

# Используемый user-agent для имитации реального браузера
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
)

# Заголовки запроса – имитируют браузерный запрос
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "User-Agent": USER_AGENT,
    "Connection": "keep-alive"
}


def adjust_category_path(category: str) -> str:
    """
    Преобразует код категории, заменяя символы (например, "_" на "-"),
    чтобы получить корректный формат URL, как на сайте OLX.kz.
    """
    return category.replace("_", "-")


def gather_links(city: str, category: str, limit: int = 1) -> list:
    """
    Собирает ссылки на страницы с объявлениями из блока ссылок на главной странице категории.
    Если нужный блок не найден, возвращает пустой список.
    """
    safe_category = adjust_category_path(category)
    base = CATEGORY_URLS.get(safe_category)
    if not base:
        print(f"[ERROR] Нет базового URL для категории {category}")
        return []
    url = f"{base}{city}/" if city != "all" else f"{base}all/"
    print(f"[INFO] Запрос: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Ошибка запроса {url}: {e}")
        return []
    soup = BeautifulSoup(response.text, "lxml")
    ul_block = soup.find("ul", {"data-testid": "category-count-links"})
    if not ul_block:
        print(f"[ERROR] CATEGORY {category.upper()} IN {city.upper()} DON'T HAVE ANY DATA")
        return []
    inner_url_links = ul_block.find_all("li")[:limit]
    print(f"[INFO] Найдено ссылок (ограничено до {limit}): {len(inner_url_links)}")
    links = []
    for li in inner_url_links:
        a_tag = li.find("a")
        if a_tag and a_tag.get("href"):
            inner_url = urljoin(BASE_URL, a_tag.get("href"))
            print(f"[INFO] Обработка ссылки: {inner_url}")
            links.append({"url": inner_url, "id": None})
    return links


def parse_ad_page(ad_url: str) -> dict:
    """
    Парсит страницу отдельного объявления с OLX.kz.

    Используется BeautifulSoup для извлечения данных:
      - Название: из тега <h4 class="css-10ofhqw">,
      - Цена: из элемента с классом "price-label",
      - Описание: из блока с id "textContent",
      - Дополнительная информация (ID объявления, продавец, адрес) – если присутствуют.

    URL объявления сохраняется в поле "Ссылка", а также извлекается ссылка на фото (если есть).

    Функция имитирует поведение обычного браузера за счёт установки корректных заголовков,
    небольших задержек и обработки ошибок.
    """
    try:
        response = requests.get(ad_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Ошибка запроса страницы {ad_url}: {e}")
        return {}

    soup = BeautifulSoup(response.text, "lxml")
    offer = soup.find("div", {"id": "offer_active"})
    if not offer:
        print("[WARNING] Контейнер объявления не найден")
        return {}

    # Извлекаем название объявления
    title_tag = offer.find("h4", {"class": "css-10ofhqw"})
    title = title_tag.get_text(strip=True) if title_tag else "Нет заголовка"

    # Извлекаем цену
    price_tag = offer.find("div", {"class": "price-label"})
    price = price_tag.get_text(strip=True) if price_tag else "Нет цены"

    # Извлекаем описание
    desc_tag = offer.find("div", {"id": "textContent"})
    description = desc_tag.get_text(strip=True) if desc_tag else "Нет описания"

    # Извлекаем идентификатор объявления (если есть)
    ad_id_tag = offer.select_one("em > small")
    ad_id = ad_id_tag.get_text(strip=True) if ad_id_tag else "Нет id"

    # Извлекаем данные продавца
    seller_tag = offer.select_one("div.offer-user__details > h4")
    seller = seller_tag.get_text(strip=True) if seller_tag else "Нет продавца"

    # Извлекаем адрес
    address_tag = offer.select_one("address > p")
    address = address_tag.get_text(strip=True) if address_tag else "Нет адреса"

    # Извлекаем фото объявления
    img_tag = offer.select_one("div#photo-gallery-opener > img")
    image = img_tag.get("src") if img_tag and img_tag.get("src") else ""

    # Телефон будет получаться через функцию get_phone (дополнительный запрос)
    phone = "Нет телефона"

    data = {
        "Название": unescape(title),
        "Цена": unescape(price),
        "Описание": unescape(description),
        "ad_id": ad_id,
        "Продавец": seller,
        "Адрес": address,
        "Ссылка": ad_url,
        "Фото": image,
        "Телефон": phone
    }
    return data


def get_phone(ad_url: str) -> str:
    """
    Извлекает номер телефона объявления.

    Функция сначала получает страницу объявления, затем ищет в скриптах токен для телефона.
    Если токен найден, формируется URL запроса номера телефона.
    Добавлена задержка для имитации реального поведения.
    Если возникает ошибка – возвращается значение "Нет телефона".
    """
    try:
        response = requests.get(ad_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Ошибка запроса для телефона {ad_url}: {e}")
        return "Нет телефона"

    soup = BeautifulSoup(response.text, "lxml")
    token = None
    for script in soup.find_all("script"):
        if "phoneToken" in script.text:
            m = re.search(r"phoneToken\s*[:=]\s*['\"]([^'\"]+)['\"]", script.text)
            if m:
                token = m.group(1)
                break
    if not token:
        print("[WARNING] Токен для телефона не найден")
        return "Нет телефона"

    phone_btn = soup.find("li", class_=lambda x: x and "link-phone" in x)
    ad_id = None
    if phone_btn and phone_btn.get("class"):
        classes = " ".join(phone_btn.get("class"))
        m = re.search(r"id['\"]?\s*:\s*['\"]([^'\"]+)['\"]", classes)
        if m:
            ad_id = m.group(1)
    if not ad_id:
        print("[WARNING] ID для телефона не найден")
        return "Нет телефона"

    time.sleep(random.uniform(5, 10))
    phone_url = f"{BASE_URL}/kz/ajax/misc/contact/phone/{ad_id}/?pt={token}"
    try:
        r_phone = requests.get(phone_url, headers=HEADERS, timeout=10)
        r_phone.raise_for_status()
        phone_soup = BeautifulSoup(r_phone.text, "lxml")
        phone_val = phone_soup.select_one("body_safe > value")
        if phone_val:
            return phone_val.get_text(strip=True)
    except Exception as e:
        print(f"[ERROR] Ошибка при получении телефона: {e}")
    return "Нет телефона"


def gather_data_and_parse(city: str, category: str, limit: int = 1) -> list:
    """
    Основная функция для сбора данных с OLX.kz.

    1. Сначала собирает ссылки на объявления через функцию gather_links.
    2. Если ссылки не найдены для указанного региона, выполняется поиск по всей стране.
    3. Для каждой ссылки вызывается parse_ad_page, затем дополнительно извлекается номер телефона.
    4. Результат – список словарей, где каждый словарь содержит полную информацию об объявлении.
    """
    links = gather_links(city, category, limit)
    if not links:
        print(f"[ERROR] CATEGORY {category.upper()} IN {city.upper()} DON'T HAVE ANY DATA")
        print("Давайте поищем по всей стране.")
        links = gather_links("all", category, limit)
        if not links:
            print(f"[ERROR] CATEGORY {category.upper()} IN ALL DON'T HAVE ANY DATA")
            return []
    dataset = []
    for link_obj in links:
        ad_url = urljoin(BASE_URL, link_obj.get("url", ""))
        print(f"[INFO] Парсинг объявления: {ad_url}")
        ad_data = parse_ad_page(ad_url)
        if not ad_data:
            continue
        phone = get_phone(ad_url)
        ad_data["Телефон"] = phone
        dataset.append(ad_data)
        print(f"[DATA] {ad_data}")
        time.sleep(1)
    return dataset


def run_parser(category_code, city_code, subcategory_code=None):
    """
    Основной синхронный парсер для OLX.kz по выбранной категории, региону и подкатегории.
    Если подкатегория не передана, используется значение "all".
    Объединяет категорию и подкатегорию через символ "/" и вызывает функцию gather_data_and_parse.
    Возвращает список объявлений.
    """
    if subcategory_code is None:
        subcategory_code = "all"
    composite_category = f"{category_code}/{subcategory_code}"
    return gather_data_and_parse(city_code, composite_category, limit=5)


if __name__ == "__main__":
    # Пример вызова для теста: для категории "prokat_tovarov/avto" в регионе "zhm" (Жамбылская)
    city = "zhm"
    category = "prokat_tovarov"
    subcategory = "avto"
    ads = gather_data_and_parse(city, f"{category}/{subcategory}", limit=1)
    print("Итоговые данные:")
    for ad in ads:
        print(ad)
