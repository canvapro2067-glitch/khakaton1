"""Нормализация адресов Гродно для геокодера."""
from __future__ import annotations

import re

REPLACEMENTS = (
    (r"сов\.?\s*пограничников", "улица Советских Пограничников"),
    (r"я\.?\s*купалы", "проспект Янки Купалы"),
    (r"л\.?\s*чайкиной", "улица Лизы Чайкиной"),
    (r"\bблк\b", "бульвар Ленинского Комсомола"),
    (r"поселок южный ул центральная", "посёлок Южный, улица Центральная"),
)


def pretty_grodno_address(address: str) -> str:
    raw = re.sub(r"\s+", " ", (address or "").strip())
    low = raw.lower().replace("ё", "е")
    for pat, repl in REPLACEMENTS:
        if re.search(pat, low):
            raw = re.sub(pat, repl, raw, flags=re.I)
            low = raw.lower().replace("ё", "е")
            break
    if re.search(r"проспект|пр-т|шоссе|переулок|бульвар|улица|\bул\.", raw, re.I):
        return raw
    m = re.match(r"^(.+?)\s+(\d+.*)$", raw)
    if m:
        return f"улица {m.group(1)}, {m.group(2)}"
    return f"улица {raw}" if raw else raw


def geocode_queries(address: str) -> list[str]:
    p = pretty_grodno_address(address)
    seen: list[str] = []
    for q in (
        f"{p}, Гродно, Беларусь",
        f"Беларусь, город Гродно, {p}",
        f"{p}, Hrodna, Belarus",
        f"{address.strip()}, Гродно, Беларусь" if address else "",
    ):
        if q and q not in seen:
            seen.append(q)
    return seen
