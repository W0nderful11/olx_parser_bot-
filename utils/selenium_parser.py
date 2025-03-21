# -*- coding: utf8 -*-
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

BASE_URL = "https://www.olx.kz"  # Используем домен OLX.kz


def get_rendered_page(url, wait_time=30):
    """
    Загружает страницу через Selenium в headless-режиме.
    Ждет появления элементов с объявлениями (селектор [data-cy='l-card']).
    Если элементы не найдены за wait_time, выводит предупреждение и возвращает полученный HTML.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    try:
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-cy='l-card']"))
        )
    except TimeoutException:
        print(f"TimeoutException: Элемент [data-cy='l-card'] не найден на {url}. Используем полученный HTML.")
    time.sleep(2)
    html = driver.page_source
    driver.quit()
    return html


def parse_ads_from_page(page_html):
    """
    Извлекает объявления со страницы с помощью BeautifulSoup.
    Если карточки объявлений (data-cy="l-card") не найдены, используется fallback‑логика для детальной страницы.
    Для каждого поля используются альтернативные селекторы.
    Если данные не извлечены, подставляются значения по умолчанию.
    Также извлекается первое найденное изображение.
    """
    soup = BeautifulSoup(page_html, 'lxml')
    ads = []
    cards = soup.find_all("div", {"data-cy": "l-card"})

    # Fallback для детальной страницы, если карточки не найдены
    if not cards:
        title = "Нет заголовка"
        price = "Нет цены"
        description = "Нет описания"
        detail_title = soup.find("div", {"data-cy": "ad_title"})
        if detail_title:
            h4 = detail_title.find("h4")
            if h4 and h4.get_text(strip=True):
                title = h4.get_text(strip=True)
        detail_price = soup.find("div", {"data-testid": "ad-price-container"})
        if detail_price:
            h3 = detail_price.find("h3", {"class": "css-fqcbii"})
            if h3 and h3.get_text(strip=True):
                price = h3.get_text(strip=True)
        detail_desc = soup.find("div", {"data-cy": "ad_description"})
        if detail_desc:
            desc_div = detail_desc.find("div", {"class": "css-19duwlz"})
            if desc_div and desc_div.get_text(strip=True):
                description = desc_div.get_text(separator="\n", strip=True)
        img_tag = soup.find("img")
        image = img_tag.get("src") if img_tag and img_tag.get("src") else "Нет фото"
        phone = "Нет телефона"
        link = "Нет ссылки"
        ads.append({
            "Название": title,
            "Цена": price,
            "Описание": description,
            "Телефон": phone,
            "Ссылка": link,
            "Фото": image
        })
        return ads

    # Стандартный вариант: парсинг карточек
    for card in cards:
        try:
            title_tag = (card.find("h4", {"class": "css-10ofhqw"}) or
                         card.find("h1") or
                         card.find("h3", {"class": "css-10ofhqw"}) or
                         card.find("span", {"class": "css-10ofhqw"}) or
                         card.find("a", {"class": "css-10ofhqw"}))
            title = title_tag.get_text(strip=True) if title_tag and title_tag.get_text(strip=True) else "Нет заголовка"
            if title == "Нет заголовка":
                detail_title = card.find("div", {"data-testid": "ad_title"})
                if detail_title:
                    h4 = detail_title.find("h4")
                    if h4 and h4.get_text(strip=True):
                        title = h4.get_text(strip=True)
            price_tag = (card.find("h3", {"class": "css-fqcbii"}) or
                         card.find("p", {"class": "price"}) or
                         card.find("span", {"class": "price"}))
            price = price_tag.get_text(strip=True) if price_tag and price_tag.get_text(strip=True) else "Нет цены"
            desc_tag = (card.find("div", {"class": "css-19duwlz"}) or
                        card.find("div", {"class": "description"}) or
                        card.find("p", {"class": "description"}))
            description = desc_tag.get_text(separator="\n", strip=True) if desc_tag and desc_tag.get_text(
                strip=True) else "Нет описания"
            phone_tag = (card.find("a", {"data-testid": "contact-phone", "class": "css-v1ndtc"}) or
                         card.find("span", {"class": "phone"}))
            phone = phone_tag.get_text(strip=True) if phone_tag and phone_tag.get_text(strip=True) else "Нет телефона"
            link_tag = card.find("a", href=True)
            link = link_tag["href"] if link_tag and link_tag.get("href") else "Нет ссылки"
            if link.startswith("/"):
                link = urljoin(BASE_URL, link)
            img_tag = card.find("img")
            image = img_tag.get("src") if img_tag and img_tag.get("src") else "Нет фото"
            ads.append({
                "Название": title,
                "Цена": price,
                "Описание": description,
                "Телефон": phone,
                "Ссылка": link,
                "Фото": image
            })
        except Exception as ex:
            print(f"Ошибка парсинга товара: {ex}")
    return ads


def selenium_parse_ads(url, limit_pages=1):
    """
    Загружает страницу по URL через Selenium,
    парсит её и возвращает итоговый текст и список объявлений.
    """
    html = get_rendered_page(url)
    ads = parse_ads_from_page(html)
    result_text = f"Найдено {len(ads)} объявлений.\n\n"
    for ad in ads:
        result_text += (
            f"Название: {ad['Название']}\n"
            f"Цена: {ad['Цена']}\n"
            f"Описание: {ad['Описание']}\n"
            f"Телефон: {ad['Телефон']}\n"
            f"Ссылка: {ad['Ссылка']}\n"
            f"Фото: {ad['Фото']}\n\n"
        )
    return result_text, ads


def run_selenium_parser(category_code, region_code, subcategory_code):
    """
    Формирует URL для выбранной категории, региона и подкатегории и запускает парсинг.
    Для "nedvizhimost" используется схема: BASE_URL/nedvizhimost/<region_code>/<subcat_url>/,
    для "stroitelstvo_remont" – BASE_URL/stroitelstvo_remont/<subcat_url>/<region_code>/,
    для остальных – BASE_URL/<category_code>/<region_code>/<subcategory_code>/.
    Если данные не найдены или все заголовки равны "Нет заголовка", выполняется fallback‑поиск.
    Для категории "uslugi" с подкатегорией "perevozki_skladskie_uslugi" fallback заменяет запрос на "перевозки".
    """
    if category_code == "nedvizhimost":
        subcat_url = subcategory_code.replace("_", "-")
        url = f"{BASE_URL}/{category_code}/{region_code}/{subcat_url}/"
    elif category_code == "stroitelstvo_remont":
        subcat_url = subcategory_code.replace("_", "-").replace("j", "y")
        url = f"{BASE_URL}/{category_code}/{subcat_url}/{region_code}/"
    else:
        url = f"{BASE_URL}/{category_code}/{region_code}/{subcategory_code}/"

    result_text, ads = selenium_parse_ads(url)
    if not ads or all(ad["Название"] == "Нет заголовка" for ad in ads):
        print("Fallback: объявления не найдены или заголовки не извлечены, выполняем поиск по запросу.")
        fallback_query = subcategory_code
        if category_code == "uslugi" and subcategory_code == "perevozki_skladskie_uslugi":
            fallback_query = "перевозки"
        result_text, ads = run_selenium_search_parser(fallback_query)
    return result_text, ads


def run_selenium_search_parser(query):
    """
    Формирует URL для поиска по запросу и использует Selenium для парсинга.
    """
    query_encoded = quote(query)
    url = f"{BASE_URL}/list/q-{query_encoded}/"
    return selenium_parse_ads(url)


def split_text(text: str, max_length: int = 4096) -> list:
    """
    Разбивает длинный текст на части для отправки в Telegram.
    """
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]
