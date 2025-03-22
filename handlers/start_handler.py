from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

start_router = Router()

def build_main_menu(user_region: str = "Не выбран") -> types.InlineKeyboardMarkup:
    keyboard = [
        [types.InlineKeyboardButton(text="Запустить парсинг OLX", callback_data="olx_parse")],
        [types.InlineKeyboardButton(text="Поиск по названию", callback_data="search")],
        [types.InlineKeyboardButton(text="Остальное", callback_data="others")],
        [types.InlineKeyboardButton(text=f"Регион: {user_region}", callback_data="change_region")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_contact_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

@start_router.message(Command("start"))
async def start_command(message: types.Message):
    text = (
        "Добро пожаловать в OLX Parser Bot!\n\n"
        "Как пользоваться:\n"
        "1. Нажмите «Запустить парсинг OLX» и выберите регион, категорию и подкатегорию (если есть).\n"
        "   После выбора бот запустит парсинг и отправит результаты.\n"
        "2. Нажмите «Поиск по названию» — бот попросит ввести запрос и покажет результаты.\n"
        "3. Для смены региона или связи с администратором нажмите «Остальное».\n\n"
        "Для регистрации отправьте контакт, нажав кнопку ниже."
    )
    contact_keyboard = build_contact_keyboard()
    await message.answer(text, reply_markup=contact_keyboard)

@start_router.message(lambda message: message.content_type == "contact")
async def process_contact(message: types.Message):
    contact = message.contact
    phone_number = contact.phone_number
    telegram_id = message.from_user.id
    username = message.from_user.username
    print(f"Зарегистрирован пользователь: {telegram_id}, {username}, {phone_number}")
    await message.answer(
        f"Спасибо! Ваш номер телефона {phone_number} успешно зарегистрирован.",
        reply_markup=ReplyKeyboardRemove()
    )
    main_menu = build_main_menu()
    await message.answer("Главное меню:", reply_markup=main_menu)
