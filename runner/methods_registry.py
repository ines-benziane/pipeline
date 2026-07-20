_REGISTRY: dict[str, type] = {}

def register(method_class):
    """Write a method in the register"""
    _REGISTRY[method_class.name] = method_class

def get(name):
    """Retrieve a method by its name"""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown method: {name}")
    method_class = _REGISTRY[name]
    return method_class()