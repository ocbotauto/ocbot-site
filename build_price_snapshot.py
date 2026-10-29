#!/usr/bin/env python3
"""Пишет price-snapshot.json: снапшот курсов монет прямо в корне сайта (same-origin).

Зачем: часть RU-мобильных операторов блокирует *.workers.dev, и цены воркера для таких
посетителей недоступны. Снапшот рядом со страницей решает это: assets/revenue.js читает
его первым слоем (дальше — живой воркер, CoinGecko, Gate.io, localStorage-кеш).

Источник — /price.json воркера ocbot-catalog (внутри него цепочка SafeTrade → CoinGecko →
Gate.io → KV-кеш; SafeTrade — биржа, где торгуются майнерские монеты каталога, и то же
место, откуда whattomine берёт их курсы). Тикеры — те, что реально используются в
каталоге (как в build_network.py).

Запуск из корня сайта:  python3 build_price_snapshot.py
Только стандартная библиотека; при недоступности воркера существующий файл не трогаем.
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "ocbot-site-build/1.0 (+https://ocbot.org)"}


def grab(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog-url", default="https://ocbot-catalog.ocbotauto.workers.dev/catalog.json")
    ap.add_argument("--coinmap-url", default="https://ocbot-catalog.ocbotauto.workers.dev/coinmap.json")
    ap.add_argument("--price-url", default="https://ocbot-catalog.ocbotauto.workers.dev/price.json")
    ap.add_argument("--out", default="price-snapshot.json")
    a = ap.parse_args()

    try:
        catalog = grab(a.catalog_url)
        coinmap = grab(a.coinmap_url).get("map", {})
    except Exception as e:
        print(f"каталог/coinmap недоступны ({e}) — существующий снапшот не трогаем")
        return 0

    # тикеры, реально используемые в каталоге (как в build_network.py), плюс сами алгоритмы
    algos = sorted({e["algo"] for e in catalog.get("entries", []) if e.get("algo")})
    tickers = sorted({coinmap[a] for a in algos if coinmap.get(a)})
    if not tickers:
        print("в каталоге нет алгоритмов с известной монетой — существующий снапшот не трогаем")
        return 0

    try:
        prices = grab(f"{a.price_url}?tickers={','.join(tickers)}")
    except Exception as e:
        print(f"/price.json недоступен ({e}) — существующий снапшот не трогаем")
        return 0
    got = (prices.get("prices") or {}) if isinstance(prices, dict) else {}
    got = {t: v for t, v in got.items() if isinstance(v, dict) and len(v)}
    if not got:
        print("воркер не отдал ни одной цены — существующий снапшот не трогаем")
        return 0

    out = {
        "format": "ocbot-price-snapshot",
        "version": 1,
        "as_of": prices.get("as_of") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "freshness": "снапшот автосборки сайта; живые курсы сайт освежает сам (см. assets/revenue.js)",
        "prices": got,
    }
    if isinstance(prices.get("sources"), dict):
        out["sources"] = {t: prices["sources"][t] for t in got if prices["sources"].get(t)}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"price-snapshot.json: {len(got)} тикер(ов): {', '.join(got)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
