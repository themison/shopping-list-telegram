import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

# Путь к базе данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")

# Имя пользователя бота
BOT_USERNAME = os.getenv("BOT_USERNAME", "grocery_list_rotor_bot")

# Максимальная длина названия списка/элемента
MAX_NAME_LENGTH = 100

# Роли пользователей
ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"

# Команды бота
COMMAND_START = "/start"
COMMAND_LISTS = "/lists"
COMMAND_ITEMS = "/items"
COMMAND_HELP = "/help"


ITEMS_PER_PAGE = 10
