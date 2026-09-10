obj = object()
name = "name"
value = getattr(obj, "name")  # noqa: B009
defaulted = getattr(obj, "name", None)
present = hasattr(obj, "name")
setattr(obj, "name", name)  # noqa: B010
