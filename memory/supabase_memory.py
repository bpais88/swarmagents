class SupabaseMemory:
    def __init__(self):
        self._store = {}

    def set(self, key, value):
        self._store[key] = value
        print(f"[Memory] Set '{key}'")

    def get(self, key):
        print(f"[Memory] Get '{key}'")
        return self._store.get(key)

memory = SupabaseMemory()
