import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from config import DATABASE_PATH, ROLE_OWNER, ROLE_EDITOR


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с базой данных"""
    conn = None
    try:
        # Создаем соединение с базой данных
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Позволяет обращаться к полям по имени
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def init_db():
    """Инициализация базы данных"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Создание таблиц
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS shopping_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                completed BOOLEAN DEFAULT FALSE,
                added_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES shopping_lists (id),
                FOREIGN KEY (added_by) REFERENCES users (id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS list_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                list_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'editor',
                invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, list_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (list_id) REFERENCES shopping_lists (id)
            )
        """
        )

        conn.commit()


def create_user(telegram_id):
    """Создание нового пользователя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (telegram_id) VALUES (?)
        """,
            (telegram_id,),
        )
        conn.commit()

        # Получаем ID созданного или существующего пользователя
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        return result["id"] if result else None


def update_user_activity(telegram_id):
    """Обновление времени последней активности пользователя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users SET last_active = ? WHERE telegram_id = ?
        """,
            (datetime.now(), telegram_id),
        )
        conn.commit()


def get_user_lists(user_id):
    """Получение всех списков пользователя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sl.id, sl.name, sl.owner_id, 
                   CASE WHEN sl.owner_id = ? THEN 'owner' ELSE la.role END as user_role
            FROM shopping_lists sl
            LEFT JOIN list_access la ON sl.id = la.list_id AND la.user_id = ?
            WHERE sl.owner_id = ? OR la.user_id = ?
            ORDER BY sl.created_at DESC
        """,
            (user_id, user_id, user_id, user_id),
        )
        return cursor.fetchall()


def create_list(name, owner_id):
    """Создание нового списка покупок"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO shopping_lists (name, owner_id) VALUES (?, ?)
        """,
            (name, owner_id),
        )
        list_id = cursor.lastrowid

        # Владелец автоматически получает доступ
        cursor.execute(
            """
            INSERT INTO list_access (user_id, list_id, role) VALUES (?, ?, ?)
        """,
            (owner_id, list_id, "owner"),
        )

        conn.commit()
        return list_id


def delete_list(list_id, user_id):
    """Удаление списка покупок (только владелец может удалить)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Проверяем, что пользователь является владельцем
        cursor.execute(
            """
            SELECT owner_id FROM shopping_lists WHERE id = ?
        """,
            (list_id,),
        )
        result = cursor.fetchone()

        if result and result["owner_id"] == user_id:
            # Удаляем список, элементы и доступы
            cursor.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            cursor.execute("DELETE FROM list_access WHERE list_id = ?", (list_id,))
            cursor.execute("DELETE FROM shopping_lists WHERE id = ?", (list_id,))
            conn.commit()
            return True
        return False


def get_list_details(list_id, user_id):
    """Получение деталей списка (если у пользователя есть доступ)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sl.id, sl.name, sl.owner_id, u.telegram_id as owner_telegram_id
            FROM shopping_lists sl
            JOIN users u ON sl.owner_id = u.id
            LEFT JOIN list_access la ON sl.id = la.list_id AND la.user_id = ?
            WHERE sl.id = ? AND (sl.owner_id = ? OR la.user_id IS NOT NULL)
        """,
            (user_id, list_id, user_id),
        )
        return cursor.fetchone()


def get_list_items(list_id):
    """Получение всех элементов списка"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, quantity, completed 
            FROM items 
            WHERE list_id = ? 
            ORDER BY created_at
        """,
            (list_id,),
        )
        return cursor.fetchall()


def add_item_to_list(list_id, item_name, quantity, user_id):
    """Добавление элемента в список"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Проверяем, существует ли уже такой элемент
        cursor.execute(
            """
            SELECT id, quantity FROM items 
            WHERE list_id = ? AND name = ? AND completed = 0
        """,
            (list_id, item_name),
        )
        existing_item = cursor.fetchone()

        if existing_item:
            # Если элемент уже существует, увеличиваем количество
            new_quantity = existing_item["quantity"] + quantity
            cursor.execute(
                """
                UPDATE items SET quantity = ? WHERE id = ?
            """,
                (new_quantity, existing_item["id"]),
            )
        else:
            # Создаем новый элемент
            cursor.execute(
                """
                INSERT INTO items (list_id, name, quantity, added_by) 
                VALUES (?, ?, ?, ?)
            """,
                (list_id, item_name, quantity, user_id),
            )

        conn.commit()


def toggle_item_completed(item_id, completed):
    """Переключение статуса выполнения элемента"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE items SET completed = ? WHERE id = ?
        """,
            (completed, item_id),
        )
        conn.commit()


def delete_item(item_id):
    """Удаление элемента из списка"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()


def clear_completed_items(list_id):
    """Удаление всех выполненных элементов из списка"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM items WHERE list_id = ? AND completed = 1", (list_id,)
        )
        conn.commit()


def invite_user_to_list(list_id, user_telegram_id, inviter_id):
    """Приглашение пользователя в список"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Проверяем, что приглашающий имеет доступ к списку
        cursor.execute(
            """
            SELECT sl.owner_id FROM shopping_lists sl
            LEFT JOIN list_access la ON sl.id = la.list_id AND la.user_id = ?
            WHERE sl.id = ? AND (sl.owner_id = ? OR la.user_id IS NOT NULL)
        """,
            (inviter_id, list_id, inviter_id),
        )

        if not cursor.fetchone():
            return False, "У вас нет доступа к этому списку"

        # Получаем ID пользователя по telegram_id
        cursor.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (user_telegram_id,)
        )
        user_result = cursor.fetchone()

        if not user_result:
            return False, "Пользователь не найден"

        user_id = user_result["id"]

        # Проверяем, не приглашен ли уже пользователь
        cursor.execute(
            """
            SELECT id FROM list_access WHERE user_id = ? AND list_id = ?
        """,
            (user_id, list_id),
        )

        if cursor.fetchone():
            return False, "Пользователь уже имеет доступ к списку"

        # Добавляем пользователя в список
        cursor.execute(
            """
            INSERT INTO list_access (user_id, list_id, role) VALUES (?, ?, ?)
        """,
            (user_id, list_id, "editor"),
        )

        conn.commit()
        return True, "Пользователь успешно приглашен"


def get_list_owner(list_id):
    """Получение владельца списка"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.telegram_id FROM shopping_lists sl
            JOIN users u ON sl.owner_id = u.id
            WHERE sl.id = ?
        """,
            (list_id,),
        )
        result = cursor.fetchone()
        return result["telegram_id"] if result else None
