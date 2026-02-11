import os
import json

from PyQt5.QtWidgets import QMessageBox

def define_sequence(bottom_line):
    # --- Формируем set и order ---
    set_dict = {}
    order_list = []
    unique_map = {}
    current_number = 1

    for stim in bottom_line:
        text = stim.base_text if hasattr(stim, "base_text") else stim
        repeats = stim.repeats if hasattr(stim, "repeats") else 1

        if not text:
            continue

        if text not in unique_map:
            unique_map[text] = current_number
            set_dict[str(current_number)] = text
            current_number += 1

        number = unique_map[text]
        order_list.extend([number] * repeats)

    new_sequence = {
        "set": set_dict,
        "order": order_list
    }
    return new_sequence


def save_sequence(filename, sequence_name, new_sequence, parent=None):
    """
    Сохраняет последовательность стимулов в JSON в формате:
    "sequence_name": {
        "set": {"1": stimulus1, "2": stimulus2, ...},
        "order": [1,2,3,...]  # с учётом повторений
    }

    bottom_line: список DraggableLabel (нижняя линия)
    """

    # --- Чтение существующего файла ---
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                data = {}
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    # --- Проверка существования sequence_name ---
    if sequence_name in data:
        reply = QMessageBox.question(
            parent,
            "Внимание",
            f"Последовательность '{sequence_name}' уже существует.\n"
            "Хотите перезаписать её?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            return  # Не сохраняем, остаёмся в окне

    # --- Перезаписываем или создаём новую ---
    
    data[sequence_name] = new_sequence

    # --- Сохраняем обратно ---
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def save_sequence_to_json(filename, sequence_name, bottom_line, parent=None):
    """
    Сохраняет последовательность стимулов в JSON в формате:
    "sequence_name": {
        "set": {"1": stimulus1, "2": stimulus2, ...},
        "order": [1,2,3,...]  # с учётом повторений
    }

    bottom_line: список DraggableLabel (нижняя линия)
    """
    new_sequence = define_sequence(bottom_line)

    # --- Чтение существующего файла ---
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                data = {}
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    # --- Проверка существования sequence_name ---
    if sequence_name in data:
        reply = QMessageBox.question(
            parent,
            "Внимание",
            f"Последовательность '{sequence_name}' уже существует.\n"
            "Хотите перезаписать её?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            return  # Не сохраняем, остаёмся в окне

    # --- Перезаписываем или создаём новую ---
    data[sequence_name] = new_sequence

    # --- Сохраняем обратно ---
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
