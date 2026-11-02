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
        s += (f"\n(фиксация частот: ядро {core}, память {mem} МГц)" if lang == "ru" else
              f"\n(clock lock: core {core}, memory {mem} MHz)")
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
    hive_btn = "Hive"
    copied = "Скопировано" if lang == "ru" else "Copied"
    power_label = "Потребл." if lang == "ru" else "Power"
    return (f'<tr><td><b>{e(mode)}</b><small>{e(en["algo"])} / {e(mname(en["miner"]))} {e(en.get("miner_version"))}</small>'
            f'{f"<small>{matched}</small>" if matched else ""}</td>'
            f'<td><div class="pre"><i>core</i> {sgn(b["core"])} &nbsp;<i>mem</i> {sgn(b["mem"])}<br><i>PL</i> {round(b["pl"])} {unit_w}{lock}</div>'
            f'<span class="cps"><button type="button" class="cp" data-copy="{e(hive_text(b, lang))}">{hive_btn}</button></span></td>'
            f'<td class="num">{num(en.get("hashrate"), 1)} <small>{unit_h}</small>{was.split("</span>")[0] + "</span>" if en.get("stock_hashrate") else ""}</td>'
            f'<td class="num">{num(en.get("power_w"), 0)} <small>{unit_w}</small></td>'
            f'<td class="num"><span class="good">{num(en.get("efficiency"), 3)}</span> <small>{unit_h.split("/")[0]}/{unit_w}</small></td>'
            f'{rev_cell}</tr>'), copied, power_label


# ---------------------------------------------------------------------------------------------------------------
# «Разгон → хешрейт»: калькулятор, график и таблица на странице модели. Данные: curves.json приёмника (замеры точек
# подбора многих карт одной модели, склеенные по шагам разгона). Таблица и график рисуются сразу в HTML (видны без JS
# и поисковикам); калькулятор работает на встроенных данных страницы — без запросов к *.workers.dev (в части сетей
# недоступен). Доход в сутки — по живому курсу монеты (assets/revenue.js) и сетевым данным network.json.
# ---------------------------------------------------------------------------------------------------------------
CURVE_TXT = {
    "ru": {"title": "Какой хешрейт даст разгон", "kicker": "Калькулятор по реальным замерам",
           "lede": "Выберите разгон — покажем, что получится на этой карте. Цифры собраны из замеров разных карт этой модели "
                   "на ригах с ботом: одна карта держит меньше, другая больше, вместе они покрывают весь диапазон.",
           "axis_core": "Ядро (core)", "axis_mem": "Память (mem)", "col_hash": "Хешрейт", "col_range": "Разброс",
           "col_pw": "Потребл.", "col_eff": "Эффективность", "col_hold": "Держат", "few": "мало данных", "heat": "перегрев",
           "none": "не держит ни одна", "cards": "карт", "w": "Вт", "of": "из", "day": "сутки",
           "t_hash": "Хешрейт", "t_pw": "Потребление", "t_eff": "Эффективность", "t_rev": "Доход в сутки", "t_hold": "Надёжность",
           "rev_note": "без учёта электричества", "rev_na": "нет курса", "hold_txt": "держат {ok} {of} {t}",
           "v_ok": "надёжно", "v_mid": "на грани: часть карт не держит", "v_bad": "высокий риск отвала",
           "v_few": "проверено мало карт", "v_none": "на этом шаге не удержалась ни одна из {t} — ставить нельзя",
           "above": "Выше {v} данных пока нет: такой разгон на этой модели ещё никто не проверял.",
           "safe": "Надёжный максимум", "peak": "Максимум хешрейта", "table": "Все шаги по замерам",
           "chart_t": "Хешрейт по шагам разгона", "legend_band": "разброс между картами", "legend_fail": "отвал",
           "pl_note": "PL у карт разный (бот задаёт его по лимиту блока питания), поэтому показан типичный PL на шаге. "
                      "Бот на вашем риге подберёт точку именно под вашу карту.",
           "minus": "Меньше", "plus": "Больше"},
    "en": {"title": "What hashrate an overclock gives", "kicker": "Calculator built from real measurements",
           "lede": "Pick an overclock to see what this card gets. The numbers come from measurements of different cards of "
                   "this model on rigs running the bot: one card holds less, another more, and together they cover the whole range.",
           "axis_core": "Core", "axis_mem": "Memory", "col_hash": "Hashrate", "col_range": "Range",
           "col_pw": "Power", "col_eff": "Efficiency", "col_hold": "Hold", "few": "few data", "heat": "overheat",
           "none": "no card holds", "cards": "cards", "w": "W", "of": "of", "day": "day",
           "t_hash": "Hashrate", "t_pw": "Power", "t_eff": "Efficiency", "t_rev": "Revenue per day", "t_hold": "Reliability",
           "rev_note": "before electricity", "rev_na": "no price", "hold_txt": "{ok} {of} {t} hold it",
           "v_ok": "reliable", "v_mid": "borderline: some cards fail", "v_bad": "high crash risk",
           "v_few": "few cards tested", "v_none": "none of the {t} held this step — do not use",
           "above": "No data above {v} yet: nobody has tested this overclock on this model.",
           "safe": "Reliable maximum", "peak": "Peak hashrate", "table": "Every measured step",
           "chart_t": "Hashrate by overclock step", "legend_band": "spread between cards", "legend_fail": "crash",
           "pl_note": "Cards run different PL (the bot sets it from the PSU budget), so the typical PL at each step is shown. "
                      "The bot on your rig tunes the point for your exact card.",
           "minus": "Less", "plus": "More"},
}


def _pct(r):
    return round(100 * r["ok"] / r["tested"]) if r["tested"] else 0


def _cls(p):
    return "good" if p >= 80 else ("warn" if p >= 50 else "bad")


def _hold_cell(r, t):
    if not r["tested"]:
        return "<td></td>"
    p = _pct(r)
    flags = []
    if r["tested"] < 3:
        flags.append(t["few"])
    if r.get("heat"):
        flags.append(t["heat"])
    fl = f'<small>{e(", ".join(flags))}</small>' if flags else ""
    return (f'<td class="num hold"><span class="hb"><span class="hf {_cls(p)}" style="width:{p}%"></span></span>'
            f'<b class="{_cls(p)}">{r["ok"]}/{r["tested"]}</b>{fl}</td>')


def _curve_table(g, axis, lang, unit_h):
    t = CURVE_TXT[lang]
    other = "mem" if axis == "core" else "core"
    head = (f'<th>{e(t["axis_" + axis])}</th><th class="num">{t["col_hash"]}</th><th class="num opt">{t["col_range"]}</th>'
            f'<th class="num">{t["col_pw"]}</th><th class="num opt">PL</th><th class="num opt">{other}</th>'
            f'<th class="num opt">{t["col_eff"]}</th><th class="num">{t["col_hold"]}</th>')
    body = []
    for r in g["axes"][axis]["rows"]:
        if r["ok"]:
            rng = f'{num(r["h_min"], 1)}–{num(r["h_max"], 1)}' if r["h_min"] != r["h_max"] else "—"
            cells = (f'<td class="num">{num(r["hashrate"], 1)} <small>{unit_h}</small></td><td class="num muted opt">{rng}</td>'
                     f'<td class="num">{num(r["power_w"], 0)} <small>{t["w"]}</small></td><td class="num opt">{e(r["pl"])}</td>'
                     f'<td class="num opt">{sgn(r[other]) if r.get(other) is not None else "—"}</td>'
                     f'<td class="num opt"><span class="good">{num(r["efficiency"], 3)}</span></td>')
        else:
            cells = (f'<td class="num bad" colspan="2">{e(t["none"])}</td>'
                     '<td class="opt"></td><td class="opt"></td><td class="opt"></td><td class="opt"></td>')
        body.append(f'<tr data-v="{r["v"]}" class="{"" if r["ok"] else "fail"}"><td><b>{sgn(r["v"])}</b></td>{cells}{_hold_cell(r, t)}</tr>')
    return f'<div class="tw"><table class="tbl curve"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _curve_chart(g, axis, lang, unit_h):
    """Статичный SVG: медиана хешрейта по шагам, полоса разброса между картами, точки цветом по «держат»."""
    t = CURVE_TXT[lang]
    rows = g["axes"][axis]["rows"]
    ok = [r for r in rows if r["ok"]]
    if len(ok) < 2:
        return ""
    W, H, L, R, T, B = 640, 220, 48, 16, 14, 34
    xs = [r["v"] for r in rows]
    x0, x1 = min(xs), max(xs)
    lo = min(r["h_min"] for r in ok)
    hi = max(r["h_max"] for r in ok)
    pad = (hi - lo) * 0.12 or hi * 0.05 or 1
    y0, y1 = lo - pad, hi + pad
    X = lambda v: L + (W - L - R) * ((v - x0) / (x1 - x0) if x1 > x0 else 0.5)
    Y = lambda h: T + (H - T - B) * (1 - (h - y0) / (y1 - y0))
    band = " ".join(f"{X(r['v']):.1f},{Y(r['h_max']):.1f}" for r in ok) + " " + \
        " ".join(f"{X(r['v']):.1f},{Y(r['h_min']):.1f}" for r in reversed(ok))
    line = " ".join(f"{X(r['v']):.1f},{Y(r['hashrate']):.1f}" for r in ok)
    grid, ticks = [], []
    for i in range(4):
        h = y0 + (y1 - y0) * (i + 0.5) / 4
        grid.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(h):.1f}" y2="{Y(h):.1f}" class="cg"/>'
                    f'<text x="{L - 6}" y="{Y(h) + 4:.1f}" text-anchor="end" class="ct">{h:.0f}</text>')
    step = max(1, len(rows) // 7)
    for r in rows[::step]:
        ticks.append(f'<text x="{X(r["v"]):.1f}" y="{H - 12}" text-anchor="middle" class="ct">{sgn(r["v"])}</text>')
    dots = []
    for r in rows:
        if r["ok"]:
            dots.append(f'<circle cx="{X(r["v"]):.1f}" cy="{Y(r["hashrate"]):.1f}" r="4.2" class="cd {_cls(_pct(r))}">'
                        f'<title>{sgn(r["v"])}: {num(r["hashrate"], 1)} {unit_h}, {r["ok"]}/{r["tested"]}</title></circle>')
        else:
            x = X(r["v"])
            dots.append(f'<path d="M{x - 4:.1f} {H - B - 8:.1f}l8 8m0-8l-8 8" class="cx"><title>{sgn(r["v"])}: {e(t["none"])}</title></path>')
    return (f'<figure class="cchart"><figcaption>{e(t["chart_t"])}, {unit_h}'
            f'<span class="lg"><i class="lgb"></i>{e(t["legend_band"])}<i class="lgx"></i>{e(t["legend_fail"])}</span></figcaption>'
            f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(t["chart_t"])}">{"".join(grid)}'
            f'<polygon points="{band}" class="cb"/><polyline points="{line}" class="cl"/>{"".join(dots)}{"".join(ticks)}'
            f'<line x1="0" x2="0" y1="{T}" y2="{H - B}" class="cm" id="cmark-{g["_i"]}-{axis}"/></svg></figure>')


def _cards_word(n, lang):
    if lang != "ru":
        return "card" if n == 1 else "cards"
    if n % 10 == 1 and n % 100 != 11:
        return "карта"
    return "карты" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "карт"


def curve_section(curves, lang, network=None, unit_h="TH/s"):
    if not curves:
        return ""
    t = CURVE_TXT[lang]
    network = network or {}
    curves = sorted(curves, key=lambda g: (-g["cards"], -max(sum(1 for r in g["axes"][a]["rows"] if r["ok"]) for a in ("core", "mem"))))
    opts, panes, data = [], [], []
    for gi, g in enumerate(curves):
        g["_i"] = gi
        label = f'{g["algo"]} · {mname(g["miner"])} {g["miner_version"]} · {g["cards"]} {_cards_word(g["cards"], lang)}'
        opts.append(f'<option value="{gi}">{e(label)}</option>')
        okn = {a: sum(1 for r in g["axes"][a]["rows"] if r["ok"]) for a in ("core", "mem")}
        axes_ok = [a for a in ("core", "mem") if okn[a] >= 2] or [g["axis"]]
        # по умолчанию — ось, по которой проверено больше шагов (при равенстве — ядро): так покупатель сразу видит
        # полную кривую, а не пару случайных шагов памяти
        g["axis"] = max(axes_ok, key=lambda a: (okn[a], a == "core"))
        for axis in axes_ok:
            hidden = "" if (gi == 0 and axis == g["axis"]) else " hidden"
            panes.append(f'<div class="cpane" data-g="{gi}" data-axis="{axis}"{hidden}>{_curve_chart(g, axis, lang, unit_h)}'
                         f'<details class="ctable" open><summary>{e(t["table"])}</summary>{_curve_table(g, axis, lang, unit_h)}</details></div>')
        n = network.get(g["algo"])
        net = None
        if n:
            try:
                net = {"k": n["hashrate_to_hs"] / n["nethash_hs"] * (86400 / n["block_time_s"]) * n["block_reward"], "coin": n["coin"]}
            except (KeyError, TypeError, ZeroDivisionError):
                net = None
        data.append({"axis": g["axis"] if g["axis"] in axes_ok else axes_ok[0], "axes": {a: g["axes"][a]["rows"] for a in axes_ok},
                     "net": net})
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    sel = (f'<label class="cfield"><span>{"Алгоритм" if lang == "ru" else "Algorithm"}</span><select id="cg">{"".join(opts)}</select></label>'
           if len(curves) > 1 else f'<span class="cgone">{e(opts[0][opts[0].index(">") + 1:-9])}</span>')
    keys = ("above", "v_ok", "v_mid", "v_bad", "v_few", "v_none", "hold_txt", "w", "of", "day", "axis_core", "axis_mem", "rev_na")
    txt = json.dumps({k: t[k] for k in keys}, ensure_ascii=False).replace("</", "<\\/")
    cur, pre, suf = ("rub", "", " ₽") if lang == "ru" else ("usd", "$", "")
    cw_js = ('var a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "карты" : "карт";' if lang == "ru"
             else 'return n === 1 ? "card" : "cards";')
    return f"""<section class="curvebox" id="curve">
  <div class="calc">
    <div class="chead"><span class="kicker">{e(t["kicker"])}</span><h2>{e(t["title"])}</h2><p class="lede">{e(t["lede"])}</p></div>
    <div class="cctl">
      {sel}
      <span class="seg" role="group"><button type="button" data-ax="core">{e(t["axis_core"])}</button><button type="button" data-ax="mem">{e(t["axis_mem"])}</button></span>
    </div>
    <div class="cinput">
      <button type="button" class="step" id="cminus" aria-label="{e(t["minus"])}">−</button>
      <label class="cval"><span id="cax">{e(t["axis_core"])}</span><input id="cval" type="number" inputmode="numeric" value="0"></label>
      <button type="button" class="step" id="cplus" aria-label="{e(t["plus"])}">+</button>
      <input id="crange" type="range" aria-label="{e(t["title"])}">
    </div>
    <div class="cpresets"><button type="button" class="chip" id="csafe">{e(t["safe"])}: <b></b></button><button type="button" class="chip" id="cpeak">{e(t["peak"])}: <b></b></button></div>
    <div class="ctiles" aria-live="polite">
      <div class="tile big"><span>{e(t["t_hash"])}</span><b id="o-h">—</b><small>{unit_h}</small></div>
      <div class="tile"><span>{e(t["t_pw"])}</span><b id="o-p">—</b><small>{e(t["w"])}</small></div>
      <div class="tile"><span>{e(t["t_eff"])}</span><b id="o-e">—</b><small>{unit_h.split("/")[0]}/{e(t["w"])}</small></div>
      <div class="tile" id="o-rev-t"><span>{e(t["t_rev"])}</span><b id="o-r">—</b><small>{e(t["rev_note"])}</small></div>
      <div class="tile hold-t"><span>{e(t["t_hold"])}</span><div class="hbig"><i id="o-hb"></i></div><b id="o-hold">—</b><small id="o-verdict"></small></div>
    </div>
    <p class="cmsg" id="cmsg" hidden></p>
  </div>
  {"".join(panes)}
  <p class="note">{e(t["pl_note"])}</p>
</section>
<script type="application/json" id="curvedata">{blob}</script>
<script>
(function () {{
  var D = JSON.parse(document.getElementById("curvedata").textContent), T = {txt};
  var gi = 0, ax = D[0].axis, v = null, sel = document.getElementById("cg"), price = {{}};
  var $ = function (id) {{ return document.getElementById(id); }};
  function sg(n) {{ n = Math.round(n); return (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n); }}
  function f(x, d) {{ return x == null || isNaN(x) ? "—" : Number(x).toFixed(d); }}
  function rows() {{ return D[gi].axes[ax] || []; }}
  function cw(n) {{ {cw_js} }}
  function pct(r) {{ return r.tested ? Math.round(100 * r.ok / r.tested) : 0; }}
  function presets() {{
    var rs = rows(), ok = rs.filter(function (r) {{ return r.ok > 0; }}), safe = null, peak = null;
    ok.forEach(function (r) {{ if (pct(r) >= 80) safe = r; if (!peak || r.hashrate > peak.hashrate) peak = r; }});
    return {{ safe: safe || ok[0], peak: peak }};
  }}
  function setup() {{
    var rs = rows(), rg = $("crange"), st = rs.length > 1 ? rs[1].v - rs[0].v : 25;
    rg.min = rs[0].v; rg.max = rs[rs.length - 1].v; rg.step = st; $("cval").step = st;
    var p = presets();
    $("csafe").querySelector("b").textContent = sg(p.safe.v); $("cpeak").querySelector("b").textContent = sg(p.peak.v);
    $("cax").textContent = T["axis_" + ax];
    document.querySelectorAll(".cpane").forEach(function (el) {{ el.hidden = !(el.getAttribute("data-g") == gi && el.getAttribute("data-axis") == ax); }});
    document.querySelectorAll("[data-ax]").forEach(function (b) {{ var a = b.getAttribute("data-ax"); b.disabled = !D[gi].axes[a]; b.classList.toggle("on", a === ax); }});
    $("o-rev-t").hidden = !D[gi].net;
    set(p.safe.v);
  }}
  function set(x) {{ v = x; $("cval").value = Math.round(x); $("crange").value = x; calc(); }}
  function mark(r) {{
    document.querySelectorAll(".cpane:not([hidden]) tr[data-v]").forEach(function (tr) {{ tr.classList.toggle("cur", r && +tr.getAttribute("data-v") === r.v); }});
    var m = $("cmark-" + gi + "-" + ax), svg = m && m.ownerSVGElement;
    if (!m) return;
    var rs = rows(), x0 = rs[0].v, x1 = rs[rs.length - 1].v, W = 640, L = 48, R = 16;
    var px = L + (W - L - R) * (x1 > x0 ? (Math.min(Math.max(v, x0), x1) - x0) / (x1 - x0) : 0.5);
    m.setAttribute("x1", px); m.setAttribute("x2", px);
  }}
  function calc() {{
    var rs = rows(), ok = rs.filter(function (r) {{ return r.ok > 0; }}), msg = $("cmsg");
    if (!rs.length || !ok.length || v == null || isNaN(v)) return;
    var maxT = rs[rs.length - 1].v, x = Math.max(v, rs[0].v);
    msg.hidden = true; msg.className = "cmsg";
    if (x > maxT) {{ msg.hidden = false; msg.classList.add("bad"); msg.textContent = T.above.replace("{{v}}", sg(maxT)); tiles(null); mark(null); return; }}
    var hr = rs.filter(function (r) {{ return r.v >= x; }})[0];       // устойчивость — по шагу не ниже введённого
    if (!hr.ok) {{ msg.hidden = false; msg.classList.add("bad"); msg.textContent = T.v_none.replace("{{t}}", hr.tested + " " + cw(hr.tested)); tiles(null, hr); mark(hr); return; }}
    var lo = null, hi = null;                                          // хешрейт — между соседними удачными шагами
    ok.forEach(function (r) {{ if (r.v <= x) lo = r; if (r.v >= x && !hi) hi = r; }});
    lo = lo || hi; hi = hi || lo;
    var k = hi.v === lo.v ? 0 : (x - lo.v) / (hi.v - lo.v);
    function mix(key) {{ var a = lo[key], b = hi[key]; return a == null ? b : b == null ? a : a + (b - a) * k; }}
    var h = mix("hashrate"), pw = mix("power_w");
    tiles({{ h: h, pw: pw, eff: pw ? h / pw : mix("efficiency") }}, hr);
    mark(hr);
  }}
  function tiles(o, hr) {{
    $("o-h").textContent = o ? f(o.h, 1) : "—"; $("o-p").textContent = o ? f(o.pw, 0) : "—"; $("o-e").textContent = o ? f(o.eff, 3) : "—";
    var net = D[gi].net, r = $("o-r");
    if (!o || !net) r.textContent = "—";
    else if (price[net.coin] != null) r.textContent = "{pre}" + (o.h * net.k * price[net.coin]).toFixed(2) + "{suf}";
    else {{ r.textContent = "…"; loadPrice(net.coin); }}
    var p = hr ? pct(hr) : 0, cls = !hr ? "" : p >= 80 ? "good" : p >= 50 ? "warn" : "bad";
    $("o-hb").style.width = (hr ? p : 0) + "%"; $("o-hb").className = cls;
    $("o-hold").textContent = hr ? p + "%" : "—"; $("o-hold").className = cls;
    $("o-verdict").textContent = !hr ? "" : T.hold_txt.replace("{{ok}}", hr.ok).replace("{{of}}", T.of).replace("{{t}}", hr.tested + " " + cw(hr.tested)) + " · " +
      (!hr.ok ? T.v_bad : hr.tested < 3 ? T.v_few : p >= 80 ? T.v_ok : p >= 50 ? T.v_mid : T.v_bad);
  }}
  var loading = {{}};
  function loadPrice(coin) {{
    if (loading[coin]) return; loading[coin] = 1;
    var go = function () {{
      if (typeof OCBotRevenue === "undefined") return setTimeout(go, 300);
      OCBotRevenue.resolvePrices([coin], "{cur}").then(function (m) {{ price[coin] = m && m[coin] != null ? m[coin] : NaN; if (isNaN(price[coin])) $("o-r").textContent = T.rev_na; else calc(); }});
    }};
    go();
  }}
  if (sel) sel.addEventListener("change", function () {{ gi = +sel.value; ax = D[gi].axis; setup(); }});
  document.querySelectorAll("[data-ax]").forEach(function (b) {{ b.addEventListener("click", function () {{ ax = b.getAttribute("data-ax"); setup(); }}); }});
  $("cval").addEventListener("input", function () {{ var x = parseFloat(this.value); if (!isNaN(x)) {{ v = x; $("crange").value = x; calc(); }} }});
  $("crange").addEventListener("input", function () {{ set(parseFloat(this.value)); }});
  $("cminus").addEventListener("click", function () {{ set((v || 0) - +$("crange").step); }});
  $("cplus").addEventListener("click", function () {{ set((v || 0) + +$("crange").step); }});
  $("csafe").addEventListener("click", function () {{ set(presets().safe.v); }});
  $("cpeak").addEventListener("click", function () {{ set(presets().peak.v); }});
  setup();
}})();
</script>"""

NAV = {
    "en": ('<nav class="navtop" aria-label="Site navigation"><a class="brand" href="index.html">{logo}<span>OCBot: auto-overclock</span></a>'
           '<a href="catalog.html">Catalog</a><a href="calculator.html">Calculator</a><a href="buy.html">Buy</a><a href="security.html">Security</a>'
           '<a href="#" onclick="try{{var u=location.pathname;u=u.replace(/\\.html$/,\'.ru.html\');'
           'localStorage.setItem(\'ocbot_lang\',\'ru\');location.href=u;}}catch(e){{}}return false;">RU</a></nav>'),
    "ru": ('<nav class="navtop" aria-label="Разделы сайта"><a class="brand" href="index.ru.html">{logo}<span>OCBot: авторазгон</span></a>'
           '<a href="catalog.ru.html">Каталог</a><a href="calculator.ru.html">Калькулятор</a><a href="buy.ru.html">Купить</a><a href="security.ru.html">Безопасность</a>'
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


def page(model, mem, entries, all_models, base, lang, network, curves=None):
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

    presets_html = (f'<div class="tw"><table class="tbl"><thead><tr>{head_cols}</tr></thead>'
                    f'<tbody>{"".join(rows_html)}</tbody></table></div>') if rows_html else ""
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
  {presets_html}
  {curve_section(curves or [], lang, network)}
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
    # дедупликация по <loc>: повторные запуски сборки не должны плодить копии одной страницы
    seen_locs = set()
    unique = []
    for b in kept:
        m = re.search(r"loc>([^<]+)</loc>", b)
        if m and m.group(1) in seen_locs:
            continue
        if m:
            seen_locs.add(m.group(1))
        unique.append(b)
    kept = unique
    fresh = "".join(sitemap_url_block(base + s + ".html", base + s + ".ru.html") for s in sorted(model_slugs))
    with open(path, "w", encoding="utf-8") as f:
        f.write(SITEMAP_HEAD + "".join(kept) + fresh + "</urlset>\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--file", default="catalog-data.json")
    ap.add_argument("--curves", default="curves-data.json")
    ap.add_argument("--curves-url", default="")
    ap.add_argument("--base", default="https://example.github.io/ocbot-site/")
    ap.add_argument("--site", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    base = a.base if a.base.endswith("/") else a.base + "/"
    if a.url:
        req = urllib.request.Request(a.url, headers={"User-Agent": "ocbot-site-build/1.0 (+https://ocbot.org)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            data = json.loads(raw.decode("utf-8"))
        # важный same-origin снапшот: сайт грузит ./catalog.json в первую
        # очередь (см. catalog.html) — без файла посетители видят устаревший каталог
        try:
            with open(os.path.join(a.site, "catalog.json"), "wb") as f:
                f.write(raw)
        except OSError:
            pass
    else:
        with open(a.file, encoding="utf-8") as f:
            data = json.load(f)
    entries = [x for x in data.get("entries", []) if x.get("best") and x.get("hashrate")]
    # таблицы «разгон → хешрейт» (необязательно: без файла страницы строятся как раньше)
    curves_by = {}
    cdoc = None
    curves_url = a.curves_url or (a.url.rsplit("/", 1)[0] + "/curves.json" if a.url else "")
    if curves_url:
        try:
            req = urllib.request.Request(curves_url, headers={"User-Agent": "ocbot-site-build/1.0 (+https://ocbot.org)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                cdoc = json.loads(r.read().decode("utf-8"))
        except Exception as ex:                       # нет кривых — страницы строятся как раньше
            print(f"curves.json недоступен ({ex}) — страницы без таблицы «разгон → хешрейт»")
    try:
        if cdoc is None:
            with open(a.curves, encoding="utf-8") as f:
                cdoc = json.load(f)
        for g in cdoc.get("curves", []):
            if any(r.get("ok") for ax in g.get("axes", {}).values() for r in ax.get("rows", [])):
                curves_by.setdefault((clean(g["model"]), g.get("mem_vendor") or ""), []).append(g)
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass
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
    for k in curves_by:
        groups.setdefault(k, [])
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
            f.write(page(model, mem, es, all_models, base, "en", network, curves_by.get((model, mem))))
        with open(os.path.join(a.site, slg + ".ru.html"), "w", encoding="utf-8") as f:
            f.write(page(model, mem, es, all_models, base, "ru", network, curves_by.get((model, mem))))

    update_sitemap(a.site, base, new_slugs)
    print(f"страниц моделей: {len(groups)} (x2 языка)")


if __name__ == "__main__":
    sys.exit(main())
