import json
import os
import requests
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Crawler:
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15'
    }

    def __init__(self, current_category, current_city):
        self.current_category = current_category
        self.current_city = current_city

    @classmethod
    def get_authorization_token(cls):
        token = ''
        while token == '':
            options = Options()
            options.add_argument('log-level=3')
            options.add_argument('--headless')
            options.page_load_strategy = 'normal'
            driver = webdriver.Edge(options=options)
            driver.get('https://www.olx.kz/')
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            time.sleep(10)
            cookies = driver.get_cookies()
            for cookie in cookies:
                if cookie['name'] == 'a_access_token':
                    token = cookie['value']
            driver.quit()
            if token:
                return token

    @classmethod
    def get_data_from_offer(cls, offer, bearer_token):
        url = f"https://www.olx.kz/api/v1/offers/{offer}/limited-phones/"
        headers = {'Authorization': f'Bearer {bearer_token}'}
        response = requests.get(url, headers=headers)
        return response.json()

    @classmethod
    def get_user_data(cls, url):
        options = Options()
        options.add_argument('log-level=3')
        options.add_argument('--headless')
        driver = webdriver.Edge(options=options)
        driver.get(f'https://www.olx.kz{url}')
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        soup = BeautifulSoup(driver.page_source, 'lxml')
        title_tag = soup.find("h4", {"class": "css-10ofhqw"}) or soup.find("h4")
        title = title_tag.text.strip() if title_tag else "Нет заголовка"
        price_tag = soup.find("h3", {"class": "css-fqcbii"}) or soup.find("p", {"class": "price"})
        price = price_tag.text.strip() if price_tag else "Нет цены"
        desc_tag = soup.find("div", {"class": "css-19duwlz"})
        description = desc_tag.get_text(separator="\n").strip() if desc_tag else "Нет описания"
        phone_tag = soup.find("a", {"data-testid": "contact-phone", "class": "css-v1ndtc"})
        phone = phone_tag.text.strip() if phone_tag else "Нет телефона"
        driver.quit()
        return title, price, description, phone

    def get_data(self):
        ids_file = f"OLX_IDS/{self.current_category}_{self.current_city}.json"
        if os.path.exists(ids_file):
            with open(ids_file, 'r', encoding='utf-8') as json_file:
                offers = json.load(json_file)
        else:
            offers = []
        bearer_token = self.get_authorization_token()
        offers_list = []
        for offer in offers:
            try:
                title, price, description, _ = self.get_user_data(offer['url'])
                try:
                    phone_data = self.get_data_from_offer(offer['id'], bearer_token)
                    phone = (phone_data['data']['phones'][0]).replace(' ', '').replace('+', '')
                except Exception:
                    phone = "Нет телефона"
                offers_list.append({
                    'id': offer.get('id', ''),
                    'name': title,
                    'price': price,
                    'description': description,
                    'phone': phone,
                    'url': offer.get('url', "Нет ссылки")
                })
            except Exception as e:
                print(f"[OLX API ERROR] Ошибка при получении данных для {offer.get('id')}: {e}")
        return offers_list
