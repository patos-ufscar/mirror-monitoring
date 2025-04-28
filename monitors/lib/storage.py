import os

def _path(key):
    return os.path.join(os.getenv('STORAGE', '/storage'), key)

def get(key : str, default : str) -> str:
    path = _path(key)
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return f.read()

def put(key : str, value : str):
    with open(_path(key), 'w') as f:
        f.write(value)

def swap(key : str, new_value : str, default : str) -> str:
    cur_value = get(key, default)
    if cur_value != new_value:
        put(key, new_value)
    return cur_value
