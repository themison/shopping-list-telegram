from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *
from utils import parse_items, format_items_list, format_lists_menu
from config import *

# Состояния для диалогов
USER_STATES = {}

STATE_WAITING_FOR_LIST_NAME = "waiting_for_list_name"
STATE_WAITING_FOR_ITEMS = "waiting_for_items"
STATE_WAITING_FOR_INVITE = "waiting_for_invite"
STATE_SELECTING_LIST = "selecting_list"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

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
    """Обработчик команды /help"""
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
        "• Отметить купленные элементы\n"
        "• Удалить элементы\n"
        "• Очистить купленные элементы\n\n"
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
    """Обработчик команды /lists"""
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    # Получаем все списки пользователя
    lists = get_user_lists(user_id)

    keyboard = [
        [InlineKeyboardButton("➕ Создать новый список", callback_data="create_list")],
    ]

    # Добавляем кнопки для каждого списка
    for i, lst in enumerate(lists):
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
    """Обработчик команды /items"""
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    # Получаем текущий список пользователя из контекста или БД
    current_list_id = context.user_data.get("current_list_id")

    if not current_list_id:
        # Пытаемся получить последний активный список
        lists = get_user_lists(user_id)
        if lists:
            current_list_id = lists[0]["id"]
            context.user_data["current_list_id"] = current_list_id
        else:
            await update.message.reply_text(
                "У вас нет активных списков. Создайте новый с помощью /lists"
            )
            return

    # Получаем детали списка
    list_details = get_list_details(current_list_id, user_id)
    if not list_details:
        await update.message.reply_text("Список не найден или у вас нет к нему доступа")
        return

    # Получаем элементы списка
    items = get_list_items(current_list_id)

    # Формируем текст сообщения
    message_text = f"*Список: {list_details['name']}*\n\n"
    message_text += format_items_list(items)

    # Создаем клавиатуру
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Добавить элементы", callback_data=f"add_items_{current_list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Отметить купленным",
                callback_data=f"mark_completed_{current_list_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить элементы", callback_data=f"delete_items_{current_list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🧹 Очистить купленные",
                callback_data=f"clear_completed_{current_list_id}",
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
    """Обработчик нажатий на кнопки"""
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
        context.user_data["current_list_id"] = list_id

        # Получаем элементы списка
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
                        "✅ Отметить купленным",
                        callback_data=f"mark_completed_{list_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🧹 Очистить купленные",
                        callback_data=f"clear_completed_{list_id}",
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
        context.user_data["current_list_id"] = list_id
        USER_STATES[user_id] = STATE_WAITING_FOR_ITEMS
        await query.edit_message_text(
            "Введите элементы для добавления (в любом формате):"
        )

    elif data.startswith("mark_completed_"):
        list_id = int(data.split("_")[2])
        context.user_data["current_list_id"] = list_id

        # Получаем невыполненные элементы
        items = get_list_items(list_id)
        pending_items = [item for item in items if not item["completed"]]

        if not pending_items:
            await query.edit_message_text("Нет элементов для отметки как купленные")
            return

        keyboard = []
        for item in pending_items:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"✅ {item['name']}"
                        + (f" x{item['quantity']}" if item["quantity"] > 1 else ""),
                        callback_data=f"complete_item_{item['id']}",
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_items_{list_id}")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Выберите элементы для отметки как купленные:", reply_markup=reply_markup
        )

    elif data.startswith("complete_item_"):
        item_id = int(data.split("_")[2])
        toggle_item_completed(item_id, True)

        # Возвращаемся к списку элементов
        list_id = context.user_data.get("current_list_id")
        if list_id:
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
                        "✅ Отметить купленным",
                        callback_data=f"mark_completed_{list_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🧹 Очистить купленные",
                        callback_data=f"clear_completed_{list_id}",
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

    elif data.startswith("delete_items_"):
        list_id = int(data.split("_")[2])
        context.user_data["current_list_id"] = list_id

        # Получаем все элементы
        items = get_list_items(list_id)

        if not items:
            await query.edit_message_text("Список пуст")
            return

        keyboard = []
        for item in items:
            status = "✅" if item["completed"] else "⭕"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status} {item['name']}"
                        + (f" x{item['quantity']}" if item["quantity"] > 1 else ""),
                        callback_data=f"delete_item_{item['id']}",
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑 Удалить всё", callback_data=f"delete_all_{list_id}"
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_items_{list_id}")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Выберите элементы для удаления:", reply_markup=reply_markup
        )

    elif data.startswith("delete_item_"):
        item_id = int(data.split("_")[2])
        delete_item(item_id)

        # Возвращаемся к списку элементов
        list_id = context.user_data.get("current_list_id")
        if list_id:
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
                        "✅ Отметить купленным",
                        callback_data=f"mark_completed_{list_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🧹 Очистить купленные",
                        callback_data=f"clear_completed_{list_id}",
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

    elif data.startswith("delete_all_"):
        list_id = int(data.split("_")[2])
        # Удаляем все элементы
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            conn.commit()

        # Возвращаемся к списку элементов
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
                    "✅ Отметить купленным", callback_data=f"mark_completed_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🧹 Очистить купленные", callback_data=f"clear_completed_{list_id}"
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

    elif data.startswith("clear_completed_"):
        list_id = int(data.split("_")[2])
        clear_completed_items(list_id)

        # Возвращаемся к списку элементов
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
                    "✅ Отметить купленным", callback_data=f"mark_completed_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🧹 Очистить купленные", callback_data=f"clear_completed_{list_id}"
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

    elif data.startswith("invite_user_"):
        list_id = int(data.split("_")[2])
        context.user_data["current_list_id"] = list_id
        USER_STATES[user_id] = STATE_WAITING_FOR_INVITE
        await query.edit_message_text(
            "Введите Telegram ID пользователя для приглашения:\n"
            "(Его можно узнать через @userinfobot)"
        )

    elif data.startswith("back_to_items_"):
        list_id = int(data.split("_")[3])
        context.user_data["current_list_id"] = list_id

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
                    "✅ Отметить купленным", callback_data=f"mark_completed_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🧹 Очистить купленные", callback_data=f"clear_completed_{list_id}"
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

    elif data == "change_list":
        # Показываем меню выбора списка
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


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    user_state = USER_STATES.get(user_id)

    if user_state == STATE_WAITING_FOR_LIST_NAME:
        # Создаем новый список
        list_name = update.message.text.strip()
        if not list_name:
            await update.message.reply_text(
                "Название списка не может быть пустым. Попробуйте еще раз:"
            )
            return

        list_id = create_list(list_name, user_id)
        context.user_data["current_list_id"] = list_id
        del USER_STATES[user_id]

        await update.message.reply_text(f"Список '{list_name}' успешно создан!")

        # Показываем меню элементов
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
                    "✅ Отметить купленным", callback_data=f"mark_completed_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить элементы", callback_data=f"delete_items_{list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🧹 Очистить купленные", callback_data=f"clear_completed_{list_id}"
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

        await update.message.reply_text(
            message_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    elif user_state == STATE_WAITING_FOR_ITEMS:
        # Добавляем элементы в список
        current_list_id = context.user_data.get("current_list_id")
        if not current_list_id:
            await update.message.reply_text("Ошибка: не выбран список")
            del USER_STATES[user_id]
            return

        # Парсим элементы
        items_to_add = parse_items(update.message.text)

        if not items_to_add:
            await update.message.reply_text(
                "Не удалось распознать элементы. Попробуйте еще раз."
            )
            return

        # Добавляем элементы в базу данных
        for item_name, quantity in items_to_add:
            add_item_to_list(current_list_id, item_name, quantity, user_id)

        del USER_STATES[user_id]

        # Показываем обновленный список
        items = get_list_items(current_list_id)
        list_details = get_list_details(current_list_id, user_id)

        message_text = f"*Список: {list_details['name']}*\n\n"
        message_text += format_items_list(items)
        message_text += f"\n\nДобавлено элементов: {len(items_to_add)}"

        keyboard = [
            [
                InlineKeyboardButton(
                    "➕ Добавить еще", callback_data=f"add_items_{current_list_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Отметить купленным",
                    callback_data=f"mark_completed_{current_list_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить элементы",
                    callback_data=f"delete_items_{current_list_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🧹 Очистить купленные",
                    callback_data=f"clear_completed_{current_list_id}",
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

    elif user_state == STATE_WAITING_FOR_INVITE:
        # Приглашаем пользователя в список
        current_list_id = context.user_data.get("current_list_id")
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
        # Обычное текстовое сообщение
        await update.message.reply_text(
            "Не понимаю команду. Используйте /help для получения справки."
        )


async def handle_start_with_params(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start с параметрами для принятия приглашения"""
    user_id = create_user(update.effective_user.id)
    update_user_activity(update.effective_user.id)

    # Проверяем наличие параметров
    if not context.args or len(context.args) < 2:
        # Обычный старт
        await start_command(update, context)
        return

    try:
        list_id = int(context.args[0])
        owner_telegram_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Неверная ссылка приглашения")
        return

    # Проверяем, что пользователь не является владельцем
    owner_id_result = None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (owner_telegram_id,)
        )
        result = cursor.fetchone()
        owner_id_result = result["id"] if result else None

    if not owner_id_result or owner_id_result == user_id:
        await update.message.reply_text("Неверная ссылка приглашения")
        return

    # Пробуем добавить пользователя в список
    success, message = invite_user_to_list(
        list_id, update.effective_user.id, owner_id_result
    )

    if success:
        await update.message.reply_text("Вы успешно присоединились к списку!")
        context.user_data["current_list_id"] = list_id
    else:
        await update.message.reply_text(f"Ошибка: {message}")
