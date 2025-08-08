from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import uuid
import hashlib
from database import *
from utils import parse_items, format_items_list, format_lists_menu
from config import *

USER_STATES = {}
USER_CURRENT_LISTS = {}

STATE_WAITING_FOR_LIST_NAME = "waiting_for_list_name"
STATE_WAITING_FOR_ITEMS = "waiting_for_items"
STATE_WAITING_FOR_INVITE = "waiting_for_invite"
STATE_SELECTING_LIST = "selecting_list"
STATE_CONTINUOUS_ADDING = "continuous_adding"


def generate_invite_token(list_id, owner_id):
    data = f"{list_id}_{owner_id}_{uuid.uuid4()}"
    token = hashlib.md5(data.encode()).hexdigest()[:16]
    return token


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    if context.args:
        token = context.args[0] if len(context.args) > 0 else None
        if token:
            invite_data = get_invite_by_token(token)
            if invite_data:
                list_id = invite_data["list_id"]
                owner_id = invite_data["owner_id"]

                success, message = invite_user_to_list_as_admin(
                    list_id, update.effective_user.id, owner_id
                )

                if success:
                    USER_CURRENT_LISTS[update.effective_user.id] = list_id
                    await update.message.reply_text(
                        f"🎉 Вы успешно присоединились к списку!\n\n"
                        f"Теперь вы являетесь администратором этого списка.\n"
                        f"Вы можете добавлять/удалять элементы и приглашать других пользователей."
                    )
                    await show_current_list_menu(update, user_id, list_id)
                    return
                else:
                    await update.message.reply_text(
                        f"Ошибка при подключении к списку: {message}"
                    )
                    return

    welcome_text = (
        "🛒 Добро пожаловать в бота для списков покупок!\n\n"
        "Доступные команды:\n"
        "/lists - управление списками\n"
        "/items - работа с элементами списка\n"
        "/help - помощь по использованию бота\n\n"
        "Создайте свой первый список покупок!"
    )

    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛒 Помощь по боту списков покупок:\n\n"
        "*Работа со списками:*\n"
        "/lists - открыть меню управления списками\n"
        "• Создать новый список\n"
        "• Выбрать существующий список\n"
        "• Удалить список (только владелец)\n"
        "• Пригласить пользователя в список\n\n"
        "*Работа с элементами:*\n"
        "/items - открыть меню работы с элементами\n"
        "• Добавить элементы (в любом формате)\n"
        "• Удалить элементы\n"
        "• Очистить список\n\n"
        "*Формат добавления элементов:*\n"
        "Поддерживаются различные разделители:\n"
        "запятая, точка с запятой, вертикальная черта,\n"
        "новая строка, табуляция\n\n"
        "Примеры:\n"
        "яблоки, молоко, хлеб\n"
        "бананы x3; йогурт x2\n"
        "картошка\n"
        "морковь x5"
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def lists_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    lists = get_user_lists(user_id)

    keyboard = [
        [InlineKeyboardButton("➕ Создать новый список", callback_data="create_list")],
    ]

    for lst in lists:
        role_icon = "👑" if lst["user_role"] == "owner" else "👥"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{role_icon} {lst['name']}",
                    callback_data=f"select_list_{lst['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        format_lists_menu(lists), reply_markup=reply_markup, parse_mode="Markdown"
    )


async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    current_list_id = USER_CURRENT_LISTS.get(user_id)

    if not current_list_id:
        lists = get_user_lists(user_id)
        if lists:
            current_list_id = lists[0]["id"]
            USER_CURRENT_LISTS[user_id] = current_list_id
        else:
            await update.message.reply_text(
                "У вас нет активных списков. Создайте новый с помощью /lists"
            )
            return

    list_details = get_list_details(current_list_id, user_id)
    if not list_details:
        await update.message.reply_text("Список не найден или у вас нет к нему доступа")
        return

    items = get_list_items(current_list_id)

    message_text = f"*Список: {list_details['name']}*\n\n"
    message_text += format_items_list(items)

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Добавить элементы", callback_data=f"add_items_{current_list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить элементы",
                callback_data=f"delete_items_{current_list_id}_page_0",
            )
        ],
        [
            InlineKeyboardButton(
                "🧨 Очистить список", callback_data=f"clear_list_{current_list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Пригласить пользователя",
                callback_data=f"invite_user_{current_list_id}",
            )
        ],
        [InlineKeyboardButton("🔄 Сменить список", callback_data="change_list")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = create_user(query.from_user.id)
    update_user_activity(query.from_user.id)

    data = query.data

    if data == "create_list":
        USER_STATES[user_id] = STATE_WAITING_FOR_LIST_NAME
        await query.edit_message_text("Введите название нового списка:")

    elif data.startswith("select_list_"):
        list_id = int(data.split("_")[2])
        USER_CURRENT_LISTS[user_id] = list_id

        items = get_list_items(list_id)
        list_details = get_list_details(list_id, user_id)

        if list_details:
            message_text = f"*Список: {list_details['name']}*\n\n"
            message_text += format_items_list(items)

            keyboard = [
                [
                    InlineKeyboardButton(
                        "➕ Добавить элементы", callback_data=f"add_items_{list_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑 Удалить элементы",
                        callback_data=f"delete_items_{list_id}_page_0",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🧨 Очистить список", callback_data=f"clear_list_{list_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "👥 Пригласить пользователя",
                        callback_data=f"invite_user_{list_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Сменить список", callback_data="change_list"
                    )
                ],
                [InlineKeyboardButton("❌ Закрыть", callback_data="close")],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                message_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("Ошибка доступа к списку")

    elif data.startswith("add_items_"):
        list_id = int(data.split("_")[2])
        USER_CURRENT_LISTS[user_id] = list_id
        USER_STATES[user_id] = STATE_CONTINUOUS_ADDING

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚪 Выйти из режима добавления",
                    callback_data=f"exit_adding_{list_id}",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Введите элементы для добавления (в любом формате).\n"
            "Вы останетесь в режиме добавления до тех пор, пока не введете другую команду "
            "или не нажмете кнопку 'Выйти из режима добавления'.",
            reply_markup=reply_markup,
        )

    elif data.startswith("exit_adding_"):
        list_id = int(data.split("_")[2])
        USER_CURRENT_LISTS[user_id] = list_id
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        await show_items_list(query, user_id, list_id)

    elif data.startswith("delete_items_"):
        parts = data.split("_")
        list_id = int(parts[2])
        page = int(parts[4]) if len(parts) > 4 else 0

        USER_CURRENT_LISTS[user_id] = list_id

        all_items = get_list_items(list_id)
        total_items = len(all_items)
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        items_page = all_items[start_idx:end_idx]

        if not items_page:
            await query.edit_message_text("Список пуст")
            return

        keyboard = []
        for item in items_page:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🗑 {item['name']}"
                        + (f" x{item['quantity']}" if item["quantity"] > 1 else ""),
                        callback_data=f"delete_single_item_{item['id']}",
                    )
                ]
            )

        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⬅️ Назад", callback_data=f"delete_items_{list_id}_page_{page-1}"
                )
            )
        if end_idx < total_items:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️ Далее", callback_data=f"delete_items_{list_id}_page_{page+1}"
                )
            )

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🧨 Удалить всё", callback_data=f"delete_all_{list_id}"
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_items_{list_id}")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Выберите элементы для удаления (страница {page+1}):\n"
            f"Показано {len(items_page)} из {total_items}",
            reply_markup=reply_markup,
        )

    elif data.startswith("delete_single_item_"):
        item_id = int(data.split("_")[3])
        delete_item(item_id)

        list_id = USER_CURRENT_LISTS.get(user_id)
        if list_id:
            await show_items_list(query, user_id, list_id)

    elif data.startswith("delete_all_"):
        list_id = int(data.split("_")[2])
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            conn.commit()

        await show_items_list(query, user_id, list_id)

    elif data.startswith("clear_list_"):
        list_id = int(data.split("_")[2])
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            conn.commit()

        await show_items_list(query, user_id, list_id)

    elif data.startswith("invite_user_"):
        list_id = int(data.split("_")[2])
        USER_CURRENT_LISTS[user_id] = list_id

        token = generate_invite_token(list_id, user_id)
        save_invite_token(token, list_id, user_id)

        invite_link = f"https://t.me/{BOT_USERNAME}?start={token}"

        await query.edit_message_text(
            f"🔗 Ссылка для приглашения в список:\n\n"
            f"`{invite_link}`\n\n"
            f"Отправьте эту ссылку тому, кого хотите пригласить.\n"
            f"Приглашенный пользователь станет администратором списка!",
            parse_mode="Markdown",
        )

    elif data.startswith("back_to_items_"):
        list_id = int(data.split("_")[3])
        USER_CURRENT_LISTS[user_id] = list_id
        await show_items_list(query, user_id, list_id)

    elif data == "change_list":
        lists = get_user_lists(user_id)

        keyboard = []
        for lst in lists:
            role_icon = "👑" if lst["user_role"] == "owner" else "👥"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{role_icon} {lst['name']}",
                        callback_data=f"select_list_{lst['id']}",
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("➕ Создать новый", callback_data="create_list")]
        )
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            format_lists_menu(lists), reply_markup=reply_markup, parse_mode="Markdown"
        )

    elif data == "close":
        await query.delete_message()

    else:
        await query.edit_message_text("Неизвестная команда")


async def show_items_list(query, user_id, list_id):
    items = get_list_items(list_id)
    list_details = get_list_details(list_id, user_id)

    message_text = f"*Список: {list_details['name']}*\n\n"
    message_text += format_items_list(items)

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Добавить элементы", callback_data=f"add_items_{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}_page_0"
            )
        ],
        [
            InlineKeyboardButton(
                "🧨 Очистить список", callback_data=f"clear_list_{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Пригласить пользователя", callback_data=f"invite_user_{list_id}"
            )
        ],
        [InlineKeyboardButton("🔄 Сменить список", callback_data="change_list")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    user_state = USER_STATES.get(user_id)

    if update.message.text.startswith("/"):
        if user_state == STATE_CONTINUOUS_ADDING:
            del USER_STATES[user_id]

    if user_state == STATE_WAITING_FOR_LIST_NAME:
        if update.message.text.lower() in ["отмена", "cancel", "/cancel"]:
            del USER_STATES[user_id]
            await update.message.reply_text("Создание списка отменено.")
            return

        list_name = update.message.text.strip()
        if not list_name:
            await update.message.reply_text(
                "Название списка не может быть пустым. Попробуйте еще раз:"
            )
            return

        list_id = create_list(list_name, user_id)
        USER_CURRENT_LISTS[user_id] = list_id
        del USER_STATES[user_id]

        await update.message.reply_text(f"Список '{list_name}' успешно создан!")

        await show_current_list_menu(update, user_id, list_id)

    elif user_state == STATE_CONTINUOUS_ADDING:
        current_list_id = USER_CURRENT_LISTS.get(user_id)
        if not current_list_id:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🚪 Выйти из режима добавления",
                        callback_data=f"exit_adding_{current_list_id or 0}",
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Ошибка: не выбран список", reply_markup=reply_markup
            )
            del USER_STATES[user_id]
            return

        items_to_add = parse_items(update.message.text)

        if not items_to_add:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🚪 Выйти из режима добавления",
                        callback_data=f"exit_adding_{current_list_id}",
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Не удалось распознать элементы.", reply_markup=reply_markup
            )
            return

        for item_name, quantity in items_to_add:
            add_item_to_list(current_list_id, item_name, quantity, user_id)

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚪 Выйти из режима добавления",
                    callback_data=f"exit_adding_{current_list_id}",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Добавлено элементов: {len(items_to_add)}", reply_markup=reply_markup
        )

    elif user_state == STATE_WAITING_FOR_ITEMS:
        current_list_id = USER_CURRENT_LISTS.get(user_id)
        if not current_list_id:
            await update.message.reply_text("Ошибка: не выбран список")
            del USER_STATES[user_id]
            return

        items_to_add = parse_items(update.message.text)

        if not items_to_add:
            await update.message.reply_text(
                "Не удалось распознать элементы. Попробуйте еще раз."
            )
            return

        for item_name, quantity in items_to_add:
            add_item_to_list(current_list_id, item_name, quantity, user_id)

        del USER_STATES[user_id]

        await show_current_list_menu(update, user_id, current_list_id)

    elif user_state == STATE_WAITING_FOR_INVITE:
        current_list_id = USER_CURRENT_LISTS.get(user_id)
        if not current_list_id:
            await update.message.reply_text("Ошибка: не выбран список")
            del USER_STATES[user_id]
            return

        try:
            invited_telegram_id = int(update.message.text.strip())
        except ValueError:
            await update.message.reply_text(
                "Неверный формат Telegram ID. Попробуйте еще раз:"
            )
            return

        success, message = invite_user_to_list(
            current_list_id, invited_telegram_id, user_id
        )

        del USER_STATES[user_id]

        if success:
            owner_telegram_id = get_list_owner(current_list_id)
            await update.message.reply_text(
                f"Пользователь успешно приглашен!\n"
                f"Отправьте ему эту ссылку для доступа к списку:\n"
                f"`/start_{current_list_id}_{owner_telegram_id}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(message)

    else:
        if update.message.text.startswith("/"):
            command = update.message.text.split()[0]
            if command == "/lists":
                await lists_command(update, context)
            elif command == "/items":
                await items_command(update, context)
            elif command == "/help":
                await help_command(update, context)
            elif command == "/start":
                await start_command(update, context)
            else:
                await update.message.reply_text(
                    "Не понимаю команду. Используйте /help для получения справки."
                )
        else:
            pass


async def show_current_list_menu(update, user_id, list_id):
    items = get_list_items(list_id)
    list_details = get_list_details(list_id, user_id)

    message_text = f"*Список: {list_details['name']}*\n\n"
    message_text += format_items_list(items)

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Добавить элементы", callback_data=f"add_items_{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}_page_0"
            )
        ],
        [
            InlineKeyboardButton(
                "🧨 Очистить список", callback_data=f"clear_list_{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Пригласить пользователя", callback_data=f"invite_user_{list_id}"
            )
        ],
        [InlineKeyboardButton("🔄 Сменить список", callback_data="change_list")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(
            message_text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            message_text, reply_markup=reply_markup, parse_mode="Markdown"
        )
