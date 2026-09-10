def public_passthrough(**kwargs):
    return kwargs


def typed_any_kwargs(count: int, **kwargs: int):
    return (count, kwargs)


async def async_passthrough(**kwargs):
    return kwargs
