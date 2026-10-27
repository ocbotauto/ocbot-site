#!/usr/bin/env python3
"""Генератор страниц моделей из общего каталога: <модель-память>.html + .ru.html в корне сайта, вписывает их в
sitemap.xml (не трогая остальные записи) и обновляет robots.txt.
Запуск из корня сайта:  python3 build_models.py --url https://ВОРКЕР/catalog.json --base https://АДРЕС_САЙТА/
Без --url берётся файл --file (по умолчанию catalog-data.json). Только стандартная библиотека."""
import argparse
import html
import json
import os
import re
import sys
import urllib.request

MODES = {
    "efficiency": ("Эффективность", "Efficiency", 0),
    "compromise": ("Компромисс", "Compromise", 1),
    "hashrate": ("Хешрейт", "Hashrate", 2),
}


def clean(m):
    return re.sub(r"\s+", " ", re.sub(r"^(NVIDIA\s+)?(GeForce\s+)?", "", str(m or ""), flags=re.I)).strip()


def slug(model, mem):
    return re.sub(r"[^a-z0-9]+", "-", (clean(model) + " " + (mem or "")).lower()).strip("-")


def mname(m):
    return re.sub(r"[-_ ]v?\d[\w.\-]*$", "", str(m or ""), flags=re.I)


def sgn(n):
    n = round(n)
    return ("+" if n > 0 else "−" if n < 0 else "") + str(abs(n))


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def hive_text(p, lang):
    s = f"Core clock: {round(p['core'])}\nMemory clock: {round(p['mem'])}\nPower limit: {round(p['pl'])} W"
    if p.get("core_lock") or p.get("mem_lock"):
        core, mem = p.get("core_lock") or "—", p.get("mem_lock") or "—"
        s += (f"\n(фиксация частот: ядро {core}, память {mem} МГц, задаётся в консоли)" if lang == "ru" else
              f"\n(clock lock: core {core}, memory {mem} MHz, set via console)")
    return s


def console_text(p, lang):
    comment = "номер карты" if lang == "ru" else "card index"
    s = (f"GPU=0   # {comment}\n" f"nvidia-smi -i $GPU -pl {round(p['pl'])}\n"
         f"DISPLAY=:0 nvidia-settings -a \"[gpu:$GPU]/GPUGraphicsClockOffsetAllPerformanceLevels={round(p['core'])}\" "
         f"-a \"[gpu:$GPU]/GPUMemoryTransferRateOffsetAllPerformanceLevels={round(p['mem'])}\"")
    if p.get("core_lock"):
        s += f"\nnvidia-smi -i $GPU -lgc {p['core_lock']},{p['core_lock']}"
    if p.get("mem_lock"):
        s += f"\nnvidia-smi -i $GPU -lmc {p['mem_lock']},{p['mem_lock']}"
    return s


def num(v, d):
    return "—" if v is None else f"{float(v):.{d}f}"


def coins_per_day(en, network):
    n = network.get(en.get("algo"))
    if not n or not en.get("hashrate"):
        return None, None
    cpd = (en["hashrate"] * n["hashrate_to_hs"] / n["nethash_hs"]) * (86400 / n["block_time_s"]) * n["block_reward"]
    return cpd, n.get("coin")


def row(en, lang, network):
    mode = MODES.get(en.get("objective") or "compromise", MODES["compromise"])[0 if lang == "ru" else 1]
    b = en["best"]
    cpd, coin = coins_per_day(en, network)
    rev_cell = f'<td class="num rev-cell" data-cpd="{cpd if cpd is not None else ""}" data-coin="{e(coin or "")}">&mdash;</td>'
    if b.get("core_lock") or b.get("mem_lock"):
        word = "фикс." if lang == "ru" else "lock"
        unit_mhz = "МГц" if lang == "ru" else "MHz"
        lock = f"<br><i>{word}</i> {e(b.get('core_lock') or '—')} / {e(b.get('mem_lock') or '—')} {unit_mhz}"
    else:
        lock = ""
    unit_h, unit_w = ("TH/s", "Вт") if lang == "ru" else ("TH/s", "W")
    was = ""
    was_word = "было" if lang == "ru" else "was"
    if en.get("stock_hashrate"):
        pct = round((en["hashrate"] - en["stock_hashrate"]) / en["stock_hashrate"] * 100)
        was = f'<span class="cost">{was_word} {num(en["stock_hashrate"], 1)} {unit_h} ({"+" if pct > 0 else ""}{pct}%)</span>'
    if en.get("stock_power_w"):
        pct = round((en["power_w"] - en["stock_power_w"]) / en["stock_power_w"] * 100)
        was += f'<span class="cost">{was_word} {num(en["stock_power_w"], 0)} {unit_w} ({"+" if pct > 0 else ""}{pct}%)</span>'
    rigs = en.get("rigs")
    if rigs:
        if lang == "ru":
            # локатив ("на 1 риге" / "на 2 ригах" / "на 21 риге") — падежные формы, в
            # отличие от именительного, не меняются по правилу 1/2-4/5+, только по тому,
            # оканчивается ли число на 1 (и не на 11): риг → риге, иначе → ригах.
            word = "риге" if rigs % 10 == 1 and rigs % 100 != 11 else "ригах"
            matched = f"✓ сработало на {rigs} {word}"
        else:
            matched = f"✓ matched on {rigs} rig{('' if rigs == 1 else 's')}"
    else:
        matched = ""
    hive_btn, console_btn = ("Hive", "Консоль") if lang == "ru" else ("Hive", "Console")
    copied = "Скопировано" if lang == "ru" else "Copied"
    power_label = "Потребл." if lang == "ru" else "Power"
    return (f'<tr><td><b>{e(mode)}</b><small>{e(en["algo"])} / {e(mname(en["miner"]))} {e(en.get("miner_version"))}</small>'
            f'{f"<small>{matched}</small>" if matched else ""}</td>'
            f'<td><div class="pre"><i>core</i> {sgn(b["core"])} &nbsp;<i>mem</i> {sgn(b["mem"])}<br><i>PL</i> {round(b["pl"])} {unit_w}{lock}</div>'
            f'<span class="cps"><button type="button" class="cp" data-copy="{e(hive_text(b, lang))}">{hive_btn}</button>'
            f'<button type="button" class="cp" data-copy="{e(console_text(b, lang))}">{console_btn}</button></span></td>'
            f'<td class="num">{num(en.get("hashrate"), 1)} <small>{unit_h}</small>{was.split("</span>")[0] + "</span>" if en.get("stock_hashrate") else ""}</td>'
            f'<td class="num">{num(en.get("power_w"), 0)} <small>{unit_w}</small></td>'
            f'<td class="num"><span class="good">{num(en.get("efficiency"), 3)}</span> <small>{unit_h.split("/")[0]}/{unit_w}</small></td>'
            f'{rev_cell}</tr>'), copied, power_label


NAV = {
    "en": ('<nav class="navtop" aria-label="Site navigation"><a class="brand" href="index.html">{logo}<span>OCBot: auto-overclock</span></a>'
           '<a href="catalog.html">Catalog</a><a href="security.html">Security</a>'
           '<a href="#" onclick="try{{var u=location.pathname;u=u.replace(/\\.html$/,\'.ru.html\');'
           'localStorage.setItem(\'ocbot_lang\',\'ru\');location.href=u;}}catch(e){{}}return false;">RU</a></nav>'),
    "ru": ('<nav class="navtop" aria-label="Разделы сайта"><a class="brand" href="index.ru.html">{logo}<span>OCBot: авторазгон</span></a>'
           '<a href="catalog.ru.html">Каталог</a><a href="security.ru.html">Безопасность</a>'
           '<a href="#" onclick="try{{var u=location.pathname;u=u.replace(/\\.ru\\.html$/,\'.html\');'
           'localStorage.setItem(\'ocbot_lang\',\'en\');location.href=u;}}catch(e){{}}return false;">EN</a></nav>'),
}
LOGO = ('<svg class="logo" viewBox="0 0 48 48" width="28" height="28" aria-hidden="true"><defs>'
        '<linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#46c8af"/>'
        '<stop offset="1" stop-color="#0c7a69"/></linearGradient></defs><rect width="48" height="48" rx="12" fill="url(#lg)"/>'
        '<rect x="9" y="15" width="30" height="18" rx="3" fill="none" stroke="#fff" stroke-width="2.4"/>'
        '<circle cx="19" cy="24" r="4.6" fill="none" stroke="#fff" stroke-width="2.2"/>'
        '<path d="M19 24l3-3" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>'
        '<path d="M28 28l3-4 3 2 3-5" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M14 36v3M20 36v3M26 36v3" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg>')


def others_links(model, mem, all_models, lang):
    ext = ".ru.html" if lang == "ru" else ".html"
    out = []
    for (m, mv) in all_models:
        if (m, mv) == (model, mem):
            continue
        label = clean(m) + (f" ({mv})" if mv else "")
        out.append(f'<a class="mlink" href="{slug(m, mv)}{ext}">{e(label)}</a>')
    return " ".join(out)


def page(model, mem, entries, all_models, base, lang, network):
    rows_out = sorted(entries, key=lambda x: (x["algo"], mname(x["miner"]), MODES.get(x.get("objective") or "compromise", MODES["compromise"])[2]))
    name = clean(model) + (f" ({mem})" if mem else "")
    slg = slug(model, mem)
    ext, other_ext = (".ru.html", ".html") if lang == "ru" else (".html", ".ru.html")
    url = base + slg + ext
    alt_url = base + slg + other_ext

    if lang == "ru":
        title = f"{name}: настройки разгона для майнинга"
        desc = (f"Проверенные пресеты разгона {name}: core, mem, power limit, хешрейт и потребление в трёх режимах. "
                "Данные присылают боты с ригов.")
        lede = "Проверенные пресеты: каждый прошёл двухчасовую проверку на риге. Эффективность, компромисс и хешрейт показаны рядом."
        back = "&larr; весь каталог"
        others_label = "Другие модели:"
        footer = ('Пресет подходит одной модели с той же памятью, майнером и версией. Перед использованием проверьте '
                   'охлаждение, райзеры и питание. Данные предоставляются «как есть», использование на ваш риск: '
                   f'<a href="{base}guide.ru.html#terms">отказ от ответственности</a>.')
        head_cols = "<th>Режим</th><th>Пресет</th><th class=\"num\">Хешрейт</th><th class=\"num\">Потребл.</th><th class=\"num\">Эффективность</th><th class=\"num\">Доход</th>"
        script_src, og_locale = "chat.js", "ru_RU"
        rev_cur, rev_prefix, rev_suffix = "rub", "", " ₽/сутки"
    else:
        title = f"{name}: mining overclock presets"
        desc = (f"Verified overclock presets for {name}: core, mem, power limit, hashrate and power draw across three "
                "modes. Data is submitted by bots running on rigs.")
        lede = "Verified presets: each one passed a two-hour test run on a rig. Efficiency, compromise and hashrate modes are shown side by side."
        back = "&larr; full catalog"
        others_label = "Other models:"
        footer = ('A preset fits one model with the same memory, miner and version. Before using it, check cooling, '
                   'risers and power delivery. Data is provided “as is”, use at your own risk: '
                   f'<a href="{base}guide.html#terms">disclaimer</a>.')
        head_cols = "<th>Mode</th><th>Preset</th><th class=\"num\">Hashrate</th><th class=\"num\">Power</th><th class=\"num\">Efficiency</th><th class=\"num\">Revenue</th>"
        script_src, og_locale = "chat.en.js", "en_US"
        rev_cur, rev_prefix, rev_suffix = "usd", "$", "/day"

    body_rows, copied, _ = "", "Copied", ""
    rows_html = []
    for x in rows_out:
        r, copied, _pw = row(x, lang, network)
        rows_html.append(r)

    redirect = ("if(L==='en')return;if(L==='ru'||(!L&&/^ru\\b/i.test(navigator.language||''))){"
                "location.replace(location.pathname.replace(/\\.html$/,'.ru.html')+location.search+location.hash);}"
                if lang == "en" else
                "if(L==='ru')return;if(L==='en'||(!L&&!/^ru\\b/i.test(navigator.language||''))){"
                "location.replace(location.pathname.replace(/\\.ru\\.html$/,'.html')+location.search+location.hash);}")

    nav = NAV[lang].format(logo=LOGO)
    others = others_links(model, mem, all_models, lang)

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<script>(function(){{try{{var L=localStorage.getItem('ocbot_lang');{redirect}}}catch(e){{}}}})();</script>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<link rel="alternate" hreflang="en" href="{e(url if lang == 'en' else alt_url)}">
<link rel="alternate" hreflang="ru" href="{e(url if lang == 'ru' else alt_url)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2048%2048%22%3E%3Crect%20width%3D%2248%22%20height%3D%2248%22%20rx%3D%2212%22%20fill%3D%22%230c7a69%22/%3E%3Crect%20x%3D%229%22%20y%3D%2215%22%20width%3D%2230%22%20height%3D%2218%22%20rx%3D%223%22%20fill%3D%22none%22%20stroke%3D%22%23fff%22%20stroke-width%3D%223%22/%3E%3Cpath%20d%3D%22M16%2028l5-6%204%203%207-8%22%20fill%3D%22none%22%20stroke%3D%22%23fff%22%20stroke-width%3D%223%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22/%3E%3C/svg%3E">
<meta name="theme-color" content="#0f7a64">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:image" content="https://ocbot.org/assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="https://ocbot.org/assets/og-image.png">
<link rel="stylesheet" href="assets/catalog.css">
</head>
<body>
<div class="wrap">
  {nav}
  <header class="hero"><div><h1>{e(name)}</h1>
  <a class="guidelink" href="{base}catalog{'.ru' if lang == 'ru' else ''}.html">{back}</a>
  <p class="lede">{lede}</p></div></header>
  <div class="tw"><table class="tbl"><thead><tr>{head_cols}</tr></thead>
  <tbody>{''.join(rows_html)}</tbody></table></div>
  <p class="others"><b>{others_label}</b> {others} </p>
  <footer>{footer}</footer>
</div>
<script>
document.addEventListener("click", function (ev) {{
  var b = ev.target.closest("[data-copy]"); if (!b) return;
  var t = b.getAttribute("data-copy"), old = b.textContent;
  function ok() {{ b.textContent = "{copied}"; setTimeout(function () {{ b.textContent = old; }}, 1400); }}
  if (navigator.clipboard) navigator.clipboard.writeText(t).then(ok, function () {{}}); else {{ var a = document.createElement("textarea"); a.value = t; document.body.appendChild(a); a.select(); try {{ document.execCommand("copy"); ok(); }} catch (x) {{}} a.remove(); }}
}});
</script>
<script src="assets/revenue.js"></script>
<script>
(function () {{
  var cells = Array.prototype.slice.call(document.querySelectorAll(".rev-cell"));
  var tickers = Array.from(new Set(cells.map(function (c) {{ return c.getAttribute("data-coin"); }}).filter(Boolean)));
  if (!tickers.length || typeof OCBotRevenue === "undefined") return;
  OCBotRevenue.resolvePrices(tickers, "{rev_cur}").then(function (priceByCoin) {{
    cells.forEach(function (c) {{
      var coin = c.getAttribute("data-coin"), cpdRaw = c.getAttribute("data-cpd"), cpd = cpdRaw ? parseFloat(cpdRaw) : null;
      var price = coin ? priceByCoin[coin] : null;
      c.textContent = (cpd && price) ? "{rev_prefix}" + (cpd * price).toFixed(2) + "{rev_suffix}" : "—";
    }});
  }});
}})();
</script>
<script src="{script_src}" defer></script>
<script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{{"token": "a903b20668564c079d7b7f6a265c0b8d"}}'></script>
</body>
</html>
"""


SITEMAP_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'


def sitemap_url_block(url_en, url_ru):
    return (f'  <url><loc>{e(url_en)}</loc><xhtml:link rel="alternate" hreflang="en" href="{e(url_en)}"/>'
            f'<xhtml:link rel="alternate" hreflang="ru" href="{e(url_ru)}"/></url>\n'
            f'  <url><loc>{e(url_ru)}</loc><xhtml:link rel="alternate" hreflang="en" href="{e(url_en)}"/>'
            f'<xhtml:link rel="alternate" hreflang="ru" href="{e(url_ru)}"/></url>\n')


def update_sitemap(site_dir, base, model_slugs):
    path = os.path.join(site_dir, "sitemap.xml")
    try:
        cur = open(path, encoding="utf-8").read()
    except OSError:
        cur = SITEMAP_HEAD + "</urlset>\n"
    blocks = re.findall(r"  <url>.*?</url>\n", cur, re.S)
    # вырезаем все старые записи о страницах моделей и об устаревшем пути catalog/<slug> — под ЛЮБЫМ доменом
    # (не только текущим base), чтобы после смены домена сайта не копились дубли-страницы со старым адресом
    kept = [b for b in blocks if not re.search(r"loc>https?://[^<]*?/(catalog/|rtx-)", b)]
    fresh = "".join(sitemap_url_block(base + s + ".html", base + s + ".ru.html") for s in sorted(model_slugs))
    with open(path, "w", encoding="utf-8") as f:
        f.write(SITEMAP_HEAD + "".join(kept) + fresh + "</urlset>\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--file", default="catalog-data.json")
    ap.add_argument("--base", default="https://example.github.io/ocbot-site/")
    ap.add_argument("--site", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    base = a.base if a.base.endswith("/") else a.base + "/"
    if a.url:
        req = urllib.request.Request(a.url, headers={"User-Agent": "ocbot-site-build/1.0 (+https://ocbot.org)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    else:
        with open(a.file, encoding="utf-8") as f:
            data = json.load(f)
    entries = [x for x in data.get("entries", []) if x.get("best") and x.get("hashrate")]
    # network.json (сетевые данные hashrate_to_hs/nethash/block_time/reward на алгоритм) живёт рядом с сайтом
    # и обновляется отдельно скриптом build_network.py; используем то, что уже лежит на диске, без похода в сеть.
    try:
        with open(os.path.join(a.site, "network.json"), encoding="utf-8") as f:
            network = json.load(f).get("coins", {})
    except (OSError, json.JSONDecodeError):
        network = {}
    groups = {}
    for x in entries:
        groups.setdefault((clean(x["model"]), x.get("mem_vendor") or ""), []).append(x)
    all_models = sorted(groups.keys())
    new_slugs = {slug(m, mv) for m, mv in all_models}

    # убираем файлы прежних моделей, которых больше нет в данных (обе языковые версии)
    for fn in os.listdir(a.site):
        m = re.match(r"^(rtx-[a-z0-9-]+)(\.ru)?\.html$", fn)
        if m and m.group(1) not in new_slugs:
            os.remove(os.path.join(a.site, fn))

    for (model, mem), es in groups.items():
        slg = slug(model, mem)
        with open(os.path.join(a.site, slg + ".html"), "w", encoding="utf-8") as f:
            f.write(page(model, mem, es, all_models, base, "en", network))
        with open(os.path.join(a.site, slg + ".ru.html"), "w", encoding="utf-8") as f:
            f.write(page(model, mem, es, all_models, base, "ru", network))

    update_sitemap(a.site, base, new_slugs)
    print(f"страниц моделей: {len(groups)} (x2 языка)")


if __name__ == "__main__":
    sys.exit(main())
