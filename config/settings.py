from environs import Env

env = Env()
env.read_env()

class settings:
    DEFAULT_USER_AGENT = env.str(
        'DEFAULT_USER_AGENT',
        default='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.91 Safari/537.36'
    )
    BASE_URL = env.str('BASE_URL', default='https://www.olx.kz/')
    PHONE_URL = env.str('PHONE_URL', default='https://www.olx.kz/ajax/misc/contact/phone/')
    # Значения по умолчанию для выбора категории, если пользователь не сделал выбор
    CATEGORY = env.str('CATEGORY', default='uslugi')
    CITY = env.str('CITY', default='abay')
    DISTRICT_ID = env.int('DISTRICT_ID', default=89)
    MIN_PRICE = env.int('MIN_PRICE', default=7000)
    MAX_PRICE = env.int('MAX_PRICE', default=10000)
    MIN_ROOMS = env.int('MIN_ROOMS', default=1)
    MAX_ROOMS = env.int('MAX_ROOMS', default=1)
    WITH_PHOTOS = int(env.bool('WITH_PHOTOS', default=True))
    WITH_PROMOTED = env.bool('WITH_PROMOTED', default=True)
    PUBLICATION_DATE = [item.lower() for item in env.list('PUBLICATION_DATE', default=['сегодня', 'вчера'])]
    TELEGRAM_BOT_API_URL = env.str('TELEGRAM_BOT_API_URL', default='https://api.telegram.org/bot')
    TELEGRAM_BOT_KEY = env.str('TELEGRAM_BOT_KEY', default=None)
    TELEGRAM_CHAT_IDS = env.list('TELEGRAM_CHAT_IDS', default=[])
    DB_NAME = 'olx_parser.db'
    LOGGER_NAME = env.str('LOG_FILENAME', default='olx_parser_log')
    LOGGING_IN_STDOUT = env.bool('LOGGING_IN_STDOUT', default=True)
    LOGGING_IN_FILE = env.bool('LOGGING_IN_FILE', default=False)
    MONTH_MAPPING = {
        'янв.': 1,
        'февр.': 2,
        'марта': 3,
        'апр.': 4,
        'мая': 5,
        'июня': 6,
        'июля': 7,
        'авг.': 8,
        'сент.': 9,
        'окт.': 10,
        'нояб.': 11,
        'дек.': 12,
    }
