#!/usr/bin/env python3
"""Пишет network.json: сетевые данные (nethash, время блока, награда) для $ -расчёта доходности
в калькуляторе. Источник — whattomine.com/coins.json (сторонний, но совпадает по формуле/единицам
с тем, что сами же проверяли вручную: см. комментарий в WHITELIST ниже).

ВАЖНО про единицы измерения: поле hashrate в catalog.json у ocbot — это "родной" хешрейт майнера для
конкретного алгоритма, а не всегда настоящие терахеши. Для алгоритма Pearl это ПРОВЕРЕНО вручную
(сверено число-в-число со страницей-калькулятором whattomine.com/coins/469-prl-pearl, где у майнеров
реально показано "207.00 Th/s @ 360W" — то есть каталог и whattomine согласны: единица — настоящие
TH/s = 1e12 H/s). Для ЛЮБОГО нового алгоритма эта сверка должна быть сделана заново вручную, иначе
легко ошибиться в единицах в тысячи раз и показать пользователю неверные деньги. Поэтому ниже —
белый список алгоритмов, для которых множитель проверен; для остальных network.json просто не
содержит записи, и калькулятор на фронтенде аккуратно скрывает $-доходность для них (а не гадает).

Запуск из корня сайта:  python3 build_network.py --coinmap-url .../coinmap.json --catalog-url .../catalog.json
"""
import argparse
import json
import sys
import urllib.request

WTM_URL = "https://whattomine.com/coins.json"
UA = {"User-Agent": "ocbot-site-build/1.0 (+https://ocbot.org)"}

# algo (как в catalog.json) -> множитель для перевода "родного" hashrate каталога в H/s.
# Добавлять новый алгоритм сюда ТОЛЬКО после ручной проверки на реальной странице whattomine.com
# (сравнить число из каталога с примером хешрейта видеокарты на их странице калькулятора).
VERIFIED_HASHRATE_TO_HS = {
    "pearl": 1e12,       # TH/s, сверено вручную 2026-10-25 c whattomine.com/coins/469-prl-pearl
    "pearlhash": 1e12,   # тот же алгоритм/монета, другое имя в каталоге
}


def grab(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coinmap-url", default="https://ocbot-catalog.ocbotauto.workers.dev/coinmap.json")
    ap.add_argument("--catalog-url", default="https://ocbot-catalog.ocbotauto.workers.dev/catalog.json")
    ap.add_argument("--out", default="network.json")
    a = ap.parse_args()

    catalog = grab(a.catalog_url)
    coinmap = grab(a.coinmap_url).get("map", {})
    algos_in_use = sorted({e["algo"] for e in catalog.get("entries", []) if e.get("algo") in VERIFIED_HASHRATE_TO_HS})

    if not algos_in_use:
        print("нет алгоритмов из белого списка в каталоге — network.json не меняем содержательно")
        wtm_by_tag = {}
    else:
        wtm = grab(WTM_URL)
        wtm_by_tag = {c.get("tag"): c for c in wtm.get("coins", {}).values() if c.get("tag")}

    coins = {}
    for algo in algos_in_use:
        tag = coinmap.get(algo)
        if not tag or tag not in wtm_by_tag:
            continue
        c = wtm_by_tag[tag]
        try:
            nethash_hs = float(c["nethash"])
            block_time_s = float(c["block_time"])
            block_reward = float(c["block_reward"])
        except (KeyError, TypeError, ValueError):
            continue
        if nethash_hs <= 0 or block_time_s <= 0 or block_reward <= 0:
            continue
        coins[algo] = {
            "coin": tag,
            "hashrate_to_hs": VERIFIED_HASHRATE_TO_HS[algo],
            "nethash_hs": nethash_hs,
            "block_time_s": block_time_s,
            "block_reward": block_reward,
            "source": "whattomine.com",
        }

    out = {"format": "ocbot-network", "version": 1, "coins": coins}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"network.json: {len(coins)} алгоритм(ов) из {len(algos_in_use)} в белом списке")


if __name__ == "__main__":
    sys.exit(main())
