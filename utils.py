import re
from typing import List, Tuple


def parse_items(text: str) -> List[Tuple[str, int]]:
    """
    Парсинг текста на элементы списка.
    Поддерживаемые разделители: запятая, точка с запятой, вертикальная черта, новая строка, табуляция

    Args:
        text (str): Текст для парсинга

    Returns:
        List[Tuple[str, int]]: Список кортежей (название_элемента, количество)
    """
    # Разделяем по всем возможным разделителям
    items_raw = re.split(r"[,;|\n\r\t]+", text.strip())

    items = []
    for item in items_raw:
        item = item.strip()
        if not item:
            continue

        # Пытаемся извлечь количество из строки вида "яблоки 5" или "хлеб x3"
        quantity_match = re.search(
            r"(?:\s+x?(\d+))|(?:\s+(\d+)\s*$)", item, re.IGNORECASE
        )
        quantity = 1

        if quantity_match:
            quantity_str = quantity_match.group(1) or quantity_match.group(2)
            if quantity_str:
                try:
                    quantity = int(quantity_str)
                except ValueError:
                    pass
            # Убираем количество из названия
            item = re.sub(r"\s+x?\d+\s*$", "", item, flags=re.IGNORECASE).strip()

        if item:
            items.append((item, quantity))

    return items


def format_items_list(items):
    """Форматирование списка элементов для отображения"""
    if not items:
        return "Список пуст"

    formatted = []
    pending_items = [item for item in items if not item["completed"]]
    completed_items = [item for item in items if item["completed"]]

    if pending_items:
        formatted.append("*Нужно купить:*")
        for item in pending_items:
            formatted.append(
                f"• {item['name']}"
                + (f" x{item['quantity']}" if item["quantity"] > 1 else "")
            )

    if completed_items:
        formatted.append("\n*Куплено:*")
        for item in completed_items:
            formatted.append(
                f"~~• {item['name']}~~"
                + (f" x{item['quantity']}" if item["quantity"] > 1 else "")
            )

    return "\n".join(formatted) if formatted else "Список пуст"


def format_lists_menu(lists):
    """Форматирование меню списков"""
    if not lists:
        return "У вас пока нет списков. Создайте новый с помощью /lists"

    formatted = ["*Ваши списки:*"]
    for i, lst in enumerate(lists, 1):
        role_icon = "👑" if lst["user_role"] == "owner" else "👥"
        formatted.append(f"{i}. {role_icon} {lst['name']}")

    formatted.append("\nВыберите список или создайте новый")
    return "\n".join(formatted)
