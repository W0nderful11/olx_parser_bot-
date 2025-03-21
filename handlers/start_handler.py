from aiogram import Router, types
from aiogram.filters import Command

start_router = Router()

def build_main_menu(user_region: str = "Не выбран") -> types.InlineKeyboardMarkup:
    keyboard = [
        [types.InlineKeyboardButton(text="Запустить парсинг OLX", callback_data="olx_parse")],
        [types.InlineKeyboardButton(text="Поиск по названию", callback_data="search")],
        [types.InlineKeyboardButton(text="Остальное", callback_data="others")],
        [types.InlineKeyboardButton(text=f"Регион: {user_region}", callback_data="change_region")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

@start_router.message(Command("start"))
async def start_command(message: types.Message):
    text = (
        "Добро пожаловать в OLX Parser Bot! !!! на данный момент ведутся тех работы!!!\n\n"
        "Как пользоваться:\n"
        "1. Нажмите «Запустить парсинг OLX» и выберите регион, затем категорию.\n"
        "   Для каждой категории отобразится меню подкатегорий – выберите нужную.\n"
        "   После выбора подкатегории бот запустит парсинг и отправит результаты.\n"
        "2. Нажмите «Поиск по названию» – бот попросит ввести запрос, а затем покажет результаты.\n"
        "3. Для смены региона или связи с администратором нажмите «Остальное».\n\n"
        "Главное меню:"
    )
    keyboard = build_main_menu()
    await message.answer(text, reply_markup=keyboard)
