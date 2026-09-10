obj = object()
name = "name"
value = getattr(obj, name)
defaulted = getattr(obj, name, None)
present = hasattr(obj, name)
setattr(obj, name, value)
direct = obj.name
