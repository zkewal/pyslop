def handle(value):
    if isinstance(value, int):
        return "int"
    elif isinstance(value, str):
        return "str"
    elif isinstance(value, float):
        return "float"
    return "other"
