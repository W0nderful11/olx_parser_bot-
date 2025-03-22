import time
from urllib.parse import urljoin, quote
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

BASE_URL = "https://www.olx.kz"


def get_rendered_page(url, wait_time=30):
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
    soup = BeautifulSoup(page_html, 'lxml')
    ads = []
    cards = soup.find_all("div", {"data-cy": "l-card"})
    for card in cards:
        try:
            title_tag = card.find("h4", {"class": "css-10ofhqw"}) or card.find("h4")
            title = title_tag.get_text(strip=True) if title_tag and title_tag.get_text(strip=True) else "Нет заголовка"
            price_tag = card.find("h3", {"class": "css-fqcbii"}) or card.find("p", {"class": "price"})
            price = price_tag.get_text(strip=True) if price_tag and price_tag.get_text(strip=True) else "Нет цены"
            desc_tag = card.find("div", {"class": "css-19duwlz"})
            description = desc_tag.get_text(separator="\n", strip=True) if desc_tag and desc_tag.get_text(
                strip=True) else "Нет описания"
            phone_tag = card.find("a", {"data-testid": "contact-phone", "class": "css-v1ndtc"})
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
        except Exception as e:
            print(f"Ошибка парсинга товара: {e}")
    return ads


def run_selenium_parser(category_code, region_code, subcategory_code):
    """
    Формирует URL для выбранной категории, подкатегории и региона по схеме:
      https://www.olx.kz/<category_code>/<(подкатегория, если не "all")>/<region_code>/
    Если подкатегория равна "all", то сегмент подкатегории не включается.
    Затем выполняется Selenium-парсинг страницы и возвращается кортеж: (result_text, ads_all).
    """
    # Если подкатегория равна "all", не включаем её в URL
    if subcategory_code == "all":
        url = f"{BASE_URL}/{category_code}/{region_code}/"
    else:
        url = f"{BASE_URL}/{category_code}/{subcategory_code}/{region_code}/"

    html = get_rendered_page(url)
    ads_all = parse_ads_from_page(html)
    result_text = f"Найдено {len(ads_all)} объявлений.\n\n"
    for ad in ads_all:
        result_text += (
            f"Название: {ad['Название']}\n"
            f"Цена: {ad['Цена']}\n"
            f"Описание: {ad['Описание']}\n"
            f"Телефон: {ad['Телефон']}\n"
            f"Ссылка: {ad['Ссылка']}\n\n"
        )
    # Если объявлений не найдено или заголовки не извлечены, выполняем fallback-поиск по запросу subcategory_code
    if not ads_all or all(ad["Название"] == "Нет заголовка" for ad in ads_all):
        print("Fallback: объявления не найдены или заголовки не извлечены, выполняем поиск по запросу.")
        result_text, ads_all = run_selenium_search_parser(subcategory_code)
    return result_text, ads_all


def run_selenium_search_parser(query):
    """
    Формирует URL для поиска по запросу и выполняет Selenium-парсинг.
    Возвращает кортеж: (result_text, ads_all)
    """
    query_encoded = quote(query)
    url = f"{BASE_URL}/list/q-{query_encoded}/"
    html = get_rendered_page(url)
    ads_all = parse_ads_from_page(html)
    result_text = f"Найдено {len(ads_all)} объявлений по запросу '{query}'.\n\n"
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
    """Разбивает длинный текст на части для отправки в Telegram."""
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]
