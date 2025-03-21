# Telegram OLX Parser Bot

Данный проект представляет собой Telegram‑бота, который парсит сайт OLX.kz, собирает данные объявлений (имя пользователя, город, номер телефона) и разделяет их по категориям. Парсинг осуществляется с обходом капчи с использованием ZenRows API, Selenium и ProxyRotator.

## Требования

- Python 3.9+
- Microsoft Edge WebDriver (для Selenium)
- Аккаунт на [ZenRows.com](https://www.zenrows.com) – необходим API ключ
- PostgreSQL (для хранения данных)

## Установка зависимостей

Установите зависимости командой:
