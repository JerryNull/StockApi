import time
import threading

CACHE_TTL = 120  # 快取 120 秒

class AccountClient:
    def __init__(self, trade_sdk):
        self.sdk              = trade_sdk
        self._inventory_cache = None
        self._inventory_ts    = 0
        self._lock            = threading.Lock()

    def get_inventory_details(self):
        with self._lock:
            age   = time.time() - self._inventory_ts
            cache = self._inventory_cache

        # 有快取就直接回傳，背景更新
        if cache is not None:
            if age >= CACHE_TTL:
                threading.Thread(target=self._refresh_cache, daemon=True).start()
            return cache

        # 無快取則同步等待
        return self._refresh_cache()

    def _refresh_cache(self):
        try:
            result = self.sdk.get_inventories()
            with self._lock:
                self._inventory_cache = result
                self._inventory_ts    = time.time()
            return result
        except Exception as e:
            with self._lock:
                if self._inventory_cache is not None:
                    return self._inventory_cache  # 失敗時回傳舊快取
            raise

    def get_account_balance(self):
        return self.sdk.get_balance()
