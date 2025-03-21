import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from html import unescape
from urllib.parse import urljoin, quote
from config.category_urls import CATEGORY_URLS

BASE_URL = "https://www.olx.kz"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36 OPR/60.0.3255.170")
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "User-Agent": USER_AGENT,
    "Connection": "keep-alive"
}


def adjust_category_path(category: str) -> str:
    return category.replace("_", "-")


def gather_links(city: str, category: str, limit: int = 1) -> list:
    safe_category = adjust_category_path(category)
    base = CATEGORY_URLS.get(safe_category)
    if not base:
        print(f"[ERROR] Нет базового URL для категории {category}")
        return []
    url = f"{base}{city}/" if city != "all" else f"{base}all/"
    print(f"[INFO] Запрос: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Ошибка запроса {url}: {e}")
        return []
    soup = BeautifulSoup(r.text, "lxml")
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
    try:
        r = requests.get(ad_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Ошибка запроса страницы {ad_url}: {e}")
        return {}
    soup = BeautifulSoup(r.text, "lxml")
    offer = soup.find("div", {"id": "offer_active"})
    if not offer:
        print("[WARNING] Контейнер объявления не найден")
        return {}
    title_tag = offer.find("h4", {"class": "css-10ofhqw"})
    title = title_tag.get_text(strip=True) if title_tag else "Нет заголовка"
    price_tag = offer.find("div", {"class": "price-label"})
    price = price_tag.get_text(strip=True) if price_tag else "Нет цены"
    desc_tag = offer.find("div", {"id": "textContent"})
    description = desc_tag.get_text(strip=True) if desc_tag else "Нет описания"
    ad_id_tag = offer.select_one("em > small")
    ad_id = ad_id_tag.get_text(strip=True) if ad_id_tag else "Нет id"
    seller_tag = offer.select_one("div.offer-user__details > h4")
    seller = seller_tag.get_text(strip=True) if seller_tag else "Нет продавца"
    address_tag = offer.select_one("address > p")
    address = address_tag.get_text(strip=True) if address_tag else "Нет адреса"
    img_tag = offer.select_one("div#photo-gallery-opener > img")
    image = img_tag.get("src") if img_tag and img_tag.get("src") else ""
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
    try:
        r = requests.get(ad_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Ошибка запроса для телефона {ad_url}: {e}")
        return "Нет телефона"
    soup = BeautifulSoup(r.text, "lxml")
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


def selenium_parse_ads(url, limit_pages=1) -> tuple:
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


def get_rendered_page(url, wait_time=30):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By  # Для селекторов
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

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
    except Exception as e:
        print(f"TimeoutException: Элемент [data-cy='l-card'] не найден на {url}. Используем полученный HTML.")
    time.sleep(2)
    html = driver.page_source
    driver.quit()
    return html


def parse_ads_from_page(page_html):
    soup = BeautifulSoup(page_html, 'lxml')
    ads = []
    cards = soup.find_all("div", {"data-cy": "l-card"})
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
            description = desc_tag.get_text(separator="\n", strip=True) if desc_tag and desc_tag.get_text(strip=True) else "Нет описания"
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


def run_selenium_search_parser(query: str) -> tuple:
    query_encoded = quote(query)
    url = f"{BASE_URL}/list/q-{query_encoded}/"
    return selenium_parse_ads(url)


def run_selenium_parser(category_code, region_code, subcategory_code) -> tuple:
    if category_code == "nedvizhimost":
        subcat_url = subcategory_code.replace("_", "-")
        url = f"{BASE_URL}/{category_code}/{region_code}/{subcat_url}/"
    elif category_code == "stroitelstvo-remont":
        subcat_url = subcategory_code.replace("_", "-").replace("j", "y")
        url = f"{BASE_URL}/{category_code}/{subcat_url}/{region_code}/"
    else:
        url = f"{BASE_URL}/{category_code}/{region_code}/{subcategory_code}/"
    print(f"[SELENIUM] Парсинг URL: {url}")
    result_text, ads = selenium_parse_ads(url)
    if not ads or all(ad["Название"] == "Нет заголовка" for ad in ads):
        print("Fallback: объявления не найдены или заголовки не извлечены, выполняем поиск по запросу.")
        fallback_query = subcategory_code
        if category_code == "uslugi" and subcategory_code == "perevozki-i-skladskie-uslugi":
            fallback_query = "перевозки"
        result_text, ads = run_selenium_search_parser(fallback_query)
    return result_text, ads


def run_parser(category_code, city_code, subcategory_code=None):
    if subcategory_code is None:
        subcategory_code = "all"
    composite_category = f"{category_code}/{subcategory_code}"
    return gather_data_and_parse(city_code, composite_category, limit=5)


def split_text(text: str, max_length: int = 4096) -> list:
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]


if __name__ == "__main__":
    from config.subcategories import SUBCATEGORY_MAPPING_FULL

    default_region = {
        "nedvizhimost": "kus",
        "uslugi": "zhetisu"
    }
    for category, subcats in SUBCATEGORY_MAPPING_FULL.items():
        region = default_region.get(category, "zhm")
        print(f"\n{'='*40}\nТест для категории: {category.upper()}, регион: {region}\n{'='*40}")
        for subcategory, subcat_name in subcats.items():
            if subcategory == "all":
                continue
            print(f"\n--- Тест для подкатегории: {subcat_name} (slug: {subcategory}) ---")
            composite_category = f"{category}/{subcategory}"
            ads = gather_data_and_parse(region, composite_category, limit=1)
            if ads:
                print("Итоговые данные:")
                for ad in ads:
                    print(ad)
            else:
                print("Объявления не найдены.")
            print("-" * 50)
