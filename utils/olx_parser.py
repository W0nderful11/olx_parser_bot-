import os
from utils.ids_gather import gather_data
from utils.crawler import Crawler
from utils.db import insert_offers_sync


def run_parser(category_code, city_code, subcategory_code=None):
    """
    Основной парсер для OLX.kz по выбранной категории (и подкатегории, если передана).
    Сначала собираем ссылки с параметром limit=1 (для тестирования), затем с помощью Crawler извлекаем подробные данные,
    сохраняем их в базу данных и возвращаем итоговый текст для Telegram с первыми 5 объявлениями.
    """
    links = gather_data(city_code, category_code, limit=1)
    crawler = Crawler(category_code, city_code)
    offers = crawler.get_data()  # Ожидается список словарей с ключами: id, name, price, description, phone, url
    insert_offers_sync(offers, category_code, city_code)

    result_text = f"Найдено {len(offers)} объявлений.\n\n"
    for offer in offers[:5]:
        result_text += (
            f"Название: {offer.get('name', 'Нет заголовка')}\n"
            f"Цена: {offer.get('price', 'Нет цены')}\n"
            f"Описание: {offer.get('description', 'Нет описания')}\n"
            f"Телефон: {offer.get('phone', 'Нет телефона')}\n"
            f"Ссылка: {offer.get('url', 'Нет ссылки')}\n\n"
        )
    return result_text


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
    User-Agent настроен под macOS.
    """
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import quote, urljoin

    BASE_URL = "https://www.olx.kz"
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
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]
