def are_equal(new_value, last_value):
    """
    Сравнивает два значения: int, str, list и другие.
    Возвращает True, если они одинаковы, иначе False.
    """
    # Если оба значения списки — сравниваем элементы рекурсивно
    if isinstance(new_value, list) and isinstance(last_value, list):
        if len(new_value) != len(last_value):
            return False
        return all(are_equal(x, y) for x, y in zip(new_value, last_value))
    
    # Для других типов используем обычное сравнение
    return new_value == last_value