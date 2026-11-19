"""Bounded local abuse protection; institutional lockout belongs to the package."""
from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from backend.app.core.errors import AppError


class LoginLimiter:
    def __init__(self, limit=20, window=300, max_keys=4096):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.entries = OrderedDict()
        self.lock = Lock()

    def check(self, address: str):
        now = monotonic()
        with self.lock:
            attempts = self.entries.pop(address, deque())
            while attempts and attempts[0] <= now - self.window:
                attempts.popleft()
            self.entries[address] = attempts
            while len(self.entries) > self.max_keys:
                self.entries.popitem(last=False)
            if len(attempts) >= self.limit:
                raise AppError('RATE_LIMITED', 'Muitas tentativas. Aguarde cinco minutos.', 429)
            attempts.append(now)
