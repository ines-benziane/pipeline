from runner.errors import MethodNotFoundError

_REGISTRY: dict[str, type] = {}

def register(method_class):
    """Write a method in the register"""
    _REGISTRY[method_class.name] = method_class

def get(name):
    """Retrieve a method by its name"""
    if name not in _REGISTRY:
        raise MethodNotFoundError(name)
    method_class = _REGISTRY[name]
    return method_class()

def list_methods():
    """Return a copy of the registered methods"""
    return dict(_REGISTRY)