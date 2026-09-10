def handle_two(value):
    if isinstance(value, int):
        return "int"
    elif isinstance(value, str):
        return "str"
    return "other"


def handle_mixed(value, other):
    if isinstance(value, int):
        return 1
    elif isinstance(other, str):
        return 2
    elif isinstance(value, float):
        return 3
    return 0
