import json
import os
import requests
from bs4 import BeautifulSoup
import time
import logging

def gather_data(city, category, limit=1, progress_callback=None):
    """
    Собирает ссылки с главной страницы категории.
    Параметр limit ограничивает количество ссылок (например, limit=1 для тестирования).
    Если нужный блок не найден, функция возвращает пустой список.
    """
    message = '[INFO] START GATHER ID FUNCTION:'
    if progress_callback:
        progress_callback(message)
    else:
        logging.info(message)

    links = []
    if not os.path.exists('OLX_IDS'):
        os.mkdir('OLX_IDS')

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15'
    }

    try:
        url = f'https://www.olx.kz/{category}/{city}/'
        logging.info(f"Запрос: {url}")
        url_response = requests.get(url=url, headers=headers, timeout=10)
    except requests.exceptions.ConnectionError:
        msg = "[ERROR] YOU HAVE BAD INTERNET CONNECTION"
        if progress_callback:
            progress_callback(msg)
        else:
            logging.error(msg)
        return []  # Возвращаем пустой список вместо exit()

    try:
        soup = BeautifulSoup(url_response.text, 'lxml')
        # Если нужный блок не найден, вернем пустой список
        ul_block = soup.find('ul', {'data-testid': 'category-count-links'})
        if not ul_block:
            raise AttributeError("Блок с ссылками не найден")
        inner_url_links = ul_block.find_all('li')[:limit]
        logging.info(f"Найдено ссылок (ограничено до {limit}): {len(inner_url_links)}")
    except AttributeError:
        msg = f"[ERROR] CATEGORY {category.upper()} IN {city.upper()} DON'T HAVE ANY DATA"
        if progress_callback:
            progress_callback(msg)
        else:
            logging.error(msg)
        return []  # Возвращаем пустой список

    for inner_url_link in inner_url_links:
        inner_url = 'https://www.olx.kz' + inner_url_link.find('a').get('href')
        logging.info(f"Обработка ссылки: {inner_url}")
        try:
            inner_url_response = requests.get(inner_url, headers=headers, timeout=10)
        except Exception as e:
            logging.warning(f"Ошибка при запросе {inner_url}: {e}")
            continue
        soup = BeautifulSoup(inner_url_response.text, 'lxml')
        try:
            page_count = soup.find_all('li', {'data-testid': 'pagination-list-item'})[-1].text
        except IndexError:
            page_count = 1
        logging.info(f"Количество страниц: {page_count}")

        for page_index in range(1, int(page_count) + 1):
            inner_page_url = inner_url + '?page=' + str(page_index)
            try:
                inner_page_url_response = requests.get(inner_page_url, headers=headers, timeout=10)
            except Exception as e:
                logging.warning(f"Ошибка при запросе {inner_page_url}: {e}")
                continue
            soup = BeautifulSoup(inner_page_url_response.text, 'lxml')
            cards = soup.find_all('div', {'data-cy': 'l-card'})
            for card in cards:
                try:
                    if int(card.get('id')):
                        links.append({
                            'url': card.find('a').get('href'),
                            'id': card.get('id')
                        })
                except (TypeError, ValueError):
                    pass

    with open(f'OLX_IDS/{category}_{city}.json', 'w', encoding='utf-8') as json_file:
        json.dump(links, json_file, indent=4, ensure_ascii=False)
    logging.info(f'[FULL COMPLETE] IDS IN {category.upper()} IS GATHER')
    return links
