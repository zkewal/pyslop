def public_passthrough(**kwargs):
    return kwargs


def typed_any_kwargs(count: int, **kwargs: int):
    return (count, kwargs)


async def async_passthrough(**kwargs):
    return kwargs


def typed_return_kwargs(count: int, **kwargs: int) -> None:
    return (count, kwargs)


async def async_return_kwargs(**kwargs) -> int:
    return 1
