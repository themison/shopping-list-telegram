import re
from typing import List, Tuple


def parse_items(text: str) -> List[Tuple[str, int]]:
    items_raw = re.split(r"[,;|\n\r\t]+", text.strip())

    items = []
    for item in items_raw:
        item = item.strip()
        if not item:
            continue

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
            item = re.sub(r"\s+x?\d+\s*$", "", item, flags=re.IGNORECASE).strip()

        if item:
            items.append((item, quantity))

    return items


def format_items_list(items):
    if not items:
        return "Список пуст"

    formatted = ["*Элементы:*"]
    for item in items:
        formatted.append(
            f"• {item['name']}"
            + (f" x{item['quantity']}" if item["quantity"] > 1 else "")
        )

    return "\n".join(formatted) if formatted else "Список пуст"


def format_lists_menu(lists):
    if not lists:
        return "У вас пока нет списков. Создайте новый с помощью /lists"

    formatted = ["*Ваши списки:*"]
    for lst in lists:
        role_icon = "👑" if lst["user_role"] == "owner" else "👥"
        formatted.append(f"{role_icon} {lst['name']}")

    formatted.append("\nВыберите список или создайте новый")
    return "\n".join(formatted)
