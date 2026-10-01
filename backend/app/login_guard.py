"""T-PUB: ograniczanie zgadywania PIN-u (D6 - aplikacja moze byc wystawiona do internetu).

Trzy warstwy:
1. adres IP - LOGIN_IP_MAX_FAILURES bledow w oknie LOGIN_IP_WINDOW blokuje IP (rosnaco do LOGIN_IP_BLOCK_MAX);
   zaufane urzadzenia nie sa blokowane po IP (inny domownik za tym samym NAT-em nie odcina ich od konta),
2. para "konto + zrodlo" (zrodlo = zaufane urzadzenie albo IP) - PAIR_MAX_ATTEMPTS bledow blokuje tylko te pare,
   wiec atakujacy blokuje siebie, a nie wlasciciela konta,
3. konto (services.py, w bazie) - przy atakach z wielu adresow; nie dotyczy zaufanych urzadzen.

Stan warstw 1 i 2 jest w pamieci procesu (jeden proces uvicorn); restart go czysci.
Adres IP klienta za reverse proxy: uvicorn --proxy-headers + FORWARDED_ALLOW_IPS (README, .env.example).
"""

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

LOGIN_IP_MAX_FAILURES = 10
LOGIN_IP_WINDOW = timedelta(minutes=15)
LOGIN_IP_BLOCK_BASE = timedelta(minutes=15)
LOGIN_IP_BLOCK_MAX = timedelta(hours=24)
LOGIN_IP_FORGET_AFTER = timedelta(hours=24)  # bez bledow przez tyle czasu - eskalacja od nowa

PAIR_MAX_ATTEMPTS = 5
PAIR_LOCK_BASE = timedelta(minutes=5)
PAIR_LOCK_MAX = timedelta(minutes=60)

_PRUNE_ABOVE = 10_000  # liczba wpisow, powyzej ktorej usuwamy przeterminowane (ochrona pamieci)


@dataclass
class _IpState:
    failures: list[datetime] = field(default_factory=list)
    blocked_until: datetime | None = None
    blocks: int = 0
    last_seen: datetime | None = None


@dataclass
class _PairState:
    failures: int = 0
    locked_until: datetime | None = None
    last_seen: datetime | None = None


class LoginBlocked(Exception):
    def __init__(self, retry_after_seconds: int, scope: str):
        super().__init__(scope)
        self.retry_after_seconds = max(1, retry_after_seconds)
        self.scope = scope  # "ip" albo "pair"


def _seconds(until: datetime, now: datetime) -> int:
    return max(1, math.ceil((until - now).total_seconds()))


class LoginGuard:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ips: dict[str, _IpState] = {}
        self._pairs: dict[str, _PairState] = {}

    def reset(self) -> None:
        with self._lock:
            self._ips.clear()
            self._pairs.clear()

    # --- sprawdzenie przed weryfikacja PIN-u ---

    def check(self, ip: str, pair_key: str, now: datetime, *, include_ip: bool = True) -> None:
        with self._lock:
            ip_state = self._ips.get(ip)
            if include_ip and ip_state and ip_state.blocked_until and ip_state.blocked_until > now:
                raise LoginBlocked(_seconds(ip_state.blocked_until, now), "ip")
            pair = self._pairs.get(pair_key)
            if pair and pair.locked_until and pair.locked_until > now:
                raise LoginBlocked(_seconds(pair.locked_until, now), "pair")

    # --- wynik weryfikacji ---

    def failure(self, ip: str, pair_key: str, now: datetime) -> tuple[int, int | None]:
        """Zapisuje blad. Zwraca (pozostale proby dla pary, sekundy blokady - jesli ta proba ja zalozyla)."""
        with self._lock:
            self._prune(now)
            locked_for = self._ip_failure(ip, now)
            pair = self._pairs.setdefault(pair_key, _PairState())
            pair.failures += 1
            pair.last_seen = now
            if pair.failures % PAIR_MAX_ATTEMPTS == 0:
                lockouts = pair.failures // PAIR_MAX_ATTEMPTS
                pair.locked_until = now + min(PAIR_LOCK_BASE * 2 ** (lockouts - 1), PAIR_LOCK_MAX)
                pair_seconds = _seconds(pair.locked_until, now)
                locked_for = max(locked_for or 0, pair_seconds)
            left = PAIR_MAX_ATTEMPTS - pair.failures % PAIR_MAX_ATTEMPTS
            return left, locked_for

    def ip_failure(self, ip: str, now: datetime) -> int | None:
        """Blad bez konta (np. zly kod pierwszego uruchomienia). Zwraca sekundy blokady IP, jesli powstala."""
        with self._lock:
            self._prune(now)
            return self._ip_failure(ip, now)

    def success(self, pair_key: str) -> None:
        with self._lock:
            self._pairs.pop(pair_key, None)

    def check_ip(self, ip: str, now: datetime) -> None:
        with self._lock:
            state = self._ips.get(ip)
            if state and state.blocked_until and state.blocked_until > now:
                raise LoginBlocked(_seconds(state.blocked_until, now), "ip")

    # --- wewnetrzne (pod self._lock) ---

    def _ip_failure(self, ip: str, now: datetime) -> int | None:
        state = self._ips.setdefault(ip, _IpState())
        if state.last_seen and now - state.last_seen > LOGIN_IP_FORGET_AFTER:
            state.blocks = 0
        state.last_seen = now
        state.failures = [moment for moment in state.failures if now - moment < LOGIN_IP_WINDOW]
        state.failures.append(now)
        if len(state.failures) < LOGIN_IP_MAX_FAILURES:
            return None
        state.failures.clear()
        state.blocks += 1
        state.blocked_until = now + min(LOGIN_IP_BLOCK_BASE * 2 ** (state.blocks - 1), LOGIN_IP_BLOCK_MAX)
        return _seconds(state.blocked_until, now)

    def _prune(self, now: datetime) -> None:
        if len(self._ips) > _PRUNE_ABOVE:
            for key in [key for key, state in self._ips.items() if state.last_seen and now - state.last_seen > LOGIN_IP_FORGET_AFTER]:
                del self._ips[key]
        if len(self._pairs) > _PRUNE_ABOVE:
            for key in [key for key, state in self._pairs.items() if state.last_seen and now - state.last_seen > LOGIN_IP_FORGET_AFTER]:
                del self._pairs[key]


guard = LoginGuard()
