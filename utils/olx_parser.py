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
    Собирает ссылки (limit передается, например, 5), затем с помощью Crawler извлекаются подробные данные,
    данные сохраняются в базу данных и возвращается итоговый текст для Telegram со структурированными объявлениями.
    """
    # Преобразуем код категории для URL (замена "_" на "-")
    category_url_code = category_code.replace("_", "-")
    # Собираем ссылки (limit=5)
    links = gather_data(city_code, category_url_code, limit=5)
    # Используем Crawler для детального парсинга объявлений по собранным ссылкам
    crawler = Crawler(category_url_code, city_code)
    offers = crawler.get_data()  # Ожидается список словарей с ключами: name, price, description, phone, url
    insert_offers_sync(offers, category_code, city_code)
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
