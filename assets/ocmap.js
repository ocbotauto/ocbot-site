/* OCBot: карта разгона на странице модели.
 * Три готовых пресета (Экономный / Рекомендуем / Максимум), простой график «хешрейт от потребления» (свой SVG,
 * лёгкий, для телефонов), 3D-вид «ядро × лимит → хешрейт» (Plotly gl3d, грузится только когда открыт 3D),
 * полная таблица по шагам ядра и проверка своего разгона.
 * Данные: <script type="application/json" id="ocmapdata"> — сырые точки подбора многих карт этой модели из
 * curves.json приёмника: [номер карты, core, mem, pl, хешрейт, Вт, ок, отвалов, перегревов].
 * Всё считается здесь, в браузере, по тем же правилам, что прототип: пресет берётся только из настроек, которые
 * держат все проверенные рядом карты; замеры на чужом лимите мощности и выбросы хешрейта отброшены. */
(function () {
  "use strict";
  var DATA_EL = document.getElementById("ocmapdata"), ROOT = document.getElementById("ocmap");
  if (!DATA_EL || !ROOT) return;
  var D = JSON.parse(DATA_EL.textContent), LANG = D.lang === "ru" ? "ru" : "en", UNIT = D.unit || "TH/s";
  var T = {
    ru: {
      kicker: "Карта разгона по реальным замерам", title: "Какой разгон поставить на " + D.model,
      lede: "Три готовых пресета из замеров бота на картах этой модели. Не хотите разбираться — берите «Рекомендуем».",
      algo: "Алгоритм и майнер", eco: "Экономный", rec: "Рекомендуем", max: "Максимум", best: "лучший выбор",
      eco_n: "меньше всего ватт на каждый " + UNIT, rec_n: "почти максимум, но без лишних ватт", max_n: "самый высокий хешрейт, который держат карты",
      vs: "{h}% хешрейта, {w}% электричества", vs_max: "эталон для сравнения", core: "Ядро", mem: "Память", pl: "Лимит",
      w: "Вт", per_w: UNIT + " на Вт", hold: "держат {a} из {b}", copy: "Скопировать", copied: "Скопировано",
      day: "/сутки", rev_note: "доход без учёта электричества", simple: "Простой", d3: "3D",
      cap2: "Каждая серая точка — один замер. Линия — лучший хешрейт при данном потреблении: выше и левее — выгоднее.",
      cap3: "Поверхность — средний хешрейт карт при разном ядре и лимите. Тяните мышью или пальцем, чтобы повернуть.",
      lg_pt: "замер", lg_line: "лучшие настройки", lg_surf: "средний хешрейт", lg_crash: "отвал",
      x2: "Потребление, Вт", y2: "Хешрейт, " + UNIT, x3: "Ядро, МГц", y3: "Лимит, Вт",
      table: "Вся таблица: от минимального до максимального разгона ядра", tsub: "шаг 25 МГц · {a}…{b} · для каждого шага лучший надёжный лимит",
      th: ["Ядро", "Память", "Лимит", UNIT, "разброс", "Вт", "Держат", ""], crash: "отвалы", few: "мало данных",
      own: "Проверить свой разгон", own_s: "оценка по замерам соседних точек", core_l: "Ядро, МГц", mem_l: "Память, МГц", pl_l: "Лимит, Вт",
      far: "Таких замеров нет — оценить нельзя. Подвиньте значения ближе к пресетам.", nodirect: "Прямых проверок рядом нет, оценка по соседним точкам.",
      all_ok: "Держат {a} из {b} проверенных карт.", some: "Держат {a} из {b} карт. Есть отвалы — снизьте ядро на 25–50 МГц.",
      cmp: "Против «Максимума»: {h}% хешрейта, {w}% ватт.", your: "ваш разгон", loading: "Загружаю 3D…", no3d: "3D не загрузился — показан простой график.",
      cards_from: "Замеры {n} {cw} {model} с разных ригов{b}. Карты обезличены.", none: "Для этого майнера пока мало проверенных точек — выберите другой.",
      dots: "точка", measured: "замер"
    },
    en: {
      kicker: "Overclock map from real measurements", title: "Which overclock to set on " + D.model,
      lede: "Three ready presets built from the bot's measurements on cards of this model. Not into details? Take “Recommended”.",
      algo: "Algorithm and miner", eco: "Economy", rec: "Recommended", max: "Maximum", best: "best pick",
      eco_n: "fewest watts per " + UNIT, rec_n: "near the maximum without wasted watts", max_n: "the highest hashrate the cards hold",
      vs: "{h}% hashrate, {w}% power", vs_max: "reference for comparison", core: "Core", mem: "Memory", pl: "Limit",
      w: "W", per_w: UNIT + " per W", hold: "{a} of {b} hold it", copy: "Copy", copied: "Copied",
      day: "/day", rev_note: "revenue before electricity", simple: "Simple", d3: "3D",
      cap2: "Each grey dot is one measurement. The line is the best hashrate at each power draw: up and to the left is better.",
      cap3: "The surface is the cards' average hashrate across core and power limit. Drag with a mouse or finger to rotate.",
      lg_pt: "measurement", lg_line: "best settings", lg_surf: "average hashrate", lg_crash: "crash",
      x2: "Power draw, W", y2: "Hashrate, " + UNIT, x3: "Core, MHz", y3: "Limit, W",
      table: "Full table: from the lowest to the highest core overclock", tsub: "25 MHz steps · {a}…{b} · best reliable limit for each step",
      th: ["Core", "Memory", "Limit", UNIT, "range", "W", "Hold", ""], crash: "crashes", few: "few data",
      own: "Check your own overclock", own_s: "estimate from nearby measurements", core_l: "Core, MHz", mem_l: "Memory, MHz", pl_l: "Limit, W",
      far: "No measurements near this point, so it can't be estimated. Move closer to the presets.", nodirect: "No direct tests nearby, estimated from neighbouring points.",
      all_ok: "{a} of {b} tested cards hold it.", some: "{a} of {b} cards hold it. Some crashed: lower the core by 25–50 MHz.",
      cmp: "Versus “Maximum”: {h}% hashrate, {w}% watts.", your: "your overclock", loading: "Loading 3D…", no3d: "3D failed to load, showing the simple chart.",
      cards_from: "Measurements of {n} {cw} {model} from different rigs{b}. Cards are anonymous.", none: "Too few verified points for this miner yet, pick another one.",
      dots: "point", measured: "measurement"
    }
  }[LANG];
  var $ = function (id) { return document.getElementById(id); };
  var css = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
  var sgn = function (v) { v = Math.round(v); return (v > 0 ? "+" : "") + v; };
  var fmt = function (v, d) { if (v == null || !isFinite(v)) return "—"; return Number(v).toLocaleString(LANG === "ru" ? "ru-RU" : "en-US", { minimumFractionDigits: d, maximumFractionDigits: d }); };
  var fill = function (s, o) { return s.replace(/\{(\w+)\}/g, function (_, k) { return o[k]; }); };
  var median = function (a) { var s = a.slice().sort(function (x, y) { return x - y; }); return s.length ? s[s.length >> 1] : null; };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var cw = function (n) { if (LANG !== "ru") return n === 1 ? "card" : "cards"; var a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "карты" : "карт"; };
  var LS = {}; try { LS = JSON.parse(localStorage.getItem("ocmap") || "{}"); } catch (e) { LS = {}; }
  var save = function () { try { localStorage.setItem("ocmap", JSON.stringify(LS)); } catch (e) { /* без памяти */ } };

  // ---------- данные ----------
  function prepare(raw) {
    var pts = raw.map(function (p) {
      return { card: p[0], core: p[1], mem: p[2], pl: p[3], h: p[4], w: p[5], ok: p[6], cr: p[7] + (p[8] || 0), kind: p[6] > 0 && p[4] ? "ok" : (p[7] + (p[8] || 0) > 0 ? "crash" : "skip") };
    }).filter(function (q) { return q.kind !== "skip"; });
    pts.forEach(function (q) {                                    // выброс хешрейта на той же карте
      if (q.kind !== "ok") return;
      var nb = pts.filter(function (o) { return o !== q && o.card === q.card && o.kind === "ok" && Math.abs(o.core - q.core) <= 75 && Math.abs(o.pl - q.pl) <= 15; }).map(function (o) { return o.h; });
      if (nb.length >= 2 && q.h < median(nb) * 0.6) q.kind = "odd";
    });
    return pts.filter(function (q) { return q.kind !== "odd"; });
  }
  function estimate(good, core, pl, mem) {
    var sw = 0, sh = 0, swp = 0, sp = 0, best = 1e9;
    for (var i = 0; i < good.length; i++) {
      var q = good[i], d2 = Math.pow((q.core - core) / 25, 2) + Math.pow((q.pl - pl) / 12, 2);
      if (mem != null) d2 += Math.pow((q.mem - mem) / 150, 2);
      if (d2 < best) best = d2;
      var wt = 1 / Math.pow(d2 + 0.15, 2); sw += wt; sh += wt * q.h; if (q.w != null) { swp += wt; sp += wt * q.w; }
    }
    return { h: sw ? sh / sw : null, w: swp ? sp / swp : null, dist: Math.sqrt(best) };
  }
  // держит ли карта ядро C при лимите около P: отвал на C или ниже — не держит; замер «ок» на C или выше — держит
  function reliability(pts, C, P) {
    var by = {}, holds = 0, tested = 0;
    pts.forEach(function (q) { if (Math.abs(q.pl - P) > 15 || Math.abs(q.core - C) > 75) return; (by[q.card] = by[q.card] || []).push(q); });
    Object.keys(by).forEach(function (c) {
      var a = by[c];
      if (a.some(function (q) { return q.kind === "crash" && q.core <= C; })) { tested++; return; }
      if (a.some(function (q) { return q.kind === "ok" && q.core >= C; })) { tested++; holds++; }
    });
    return { holds: holds, tested: tested };
  }
  function analyse(g) {
    var pts = g.P, good = pts.filter(function (q) { return q.kind === "ok"; });
    var res = { cand: [], ok: [], presets: [], frontier: [], max: null };
    if (good.length < 3) return res;
    var cores = good.map(function (q) { return q.core; }), pls = good.map(function (q) { return q.pl; });
    var c0 = Math.min.apply(null, cores), c1 = Math.max.apply(null, cores), p0 = Math.min.apply(null, pls), p1 = Math.max.apply(null, pls);
    var nCards = new Set(pts.map(function (q) { return q.card; })).size, memAll = median(good.map(function (q) { return q.mem; }));
    for (var C = Math.ceil(c0 / 25) * 25; C <= c1; C += 25) for (var P = Math.ceil(p0 / 5) * 5; P <= p1; P += 5) {
      var e = estimate(good, C, P); if (e.dist > 1.0 || e.h == null) continue;
      var r = reliability(pts, C, P);
      var near = good.filter(function (q) { return Math.abs(q.core - C) <= 25 && Math.abs(q.pl - P) <= 10; }).map(function (q) { return q.mem; });
      var mem = Math.round((near.length ? median(near) : memAll) / 50) * 50, w = Math.min(e.w == null ? P : e.w, P);
      res.cand.push({ core: C, pl: P, mem: mem, h: e.h, w: w, eff: e.h / w, holds: r.holds, tested: r.tested });
    }
    var need = Math.min(2, nCards);
    var ok = res.cand.filter(function (c) { return c.tested >= need && c.holds === c.tested; });
    if (ok.length < 3) ok = res.cand.filter(function (c) { return c.tested >= need && c.holds / c.tested >= 0.75; });
    if (ok.length < 3) ok = res.cand.filter(function (c) { return c.tested >= 1 && c.holds === c.tested; });
    res.ok = ok;
    if (!ok.length) return res;
    var max = ok.reduce(function (a, b) { return b.h > a.h || (b.h === a.h && b.w < a.w) ? b : a; });
    var bestEff = function (list) { return list.reduce(function (a, b) { return b.eff > a.eff ? b : a; }); };
    var rec = bestEff(ok.filter(function (c) { return c.h >= max.h * 0.96; }));
    var eco = bestEff(ok.filter(function (c) { return c.h >= max.h * 0.8; }));
    res.max = max;
    res.presets = [Object.assign({ id: "eco" }, eco), Object.assign({ id: "rec" }, rec), Object.assign({ id: "max" }, max)];
    var top = -1;
    ok.slice().sort(function (a, b) { return a.w - b.w || b.h - a.h; }).forEach(function (c) { if (c.h > top + 0.05) { res.frontier.push(c); top = c.h; } });
    return res;
  }
  D.groups.forEach(function (g) { g.P = prepare(g.pts || []); g.A = analyse(g); });
  var groups = D.groups.filter(function (g) { return g.A.presets.length; });
  if (!groups.length) return;                                     // остаётся статичная таблица из HTML
  groups.sort(function (a, b) { return b.cards - a.cards || b.P.length - a.P.length; });

  var webgl = (function () { try { var c = document.createElement("canvas"); return !!(c.getContext("webgl") || c.getContext("experimental-webgl")); } catch (e) { return false; } })();
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  var st = { g: groups.filter(function (g) { return g.id === LS.g; })[0] || groups[0], sel: "rec", own: null,
             mode: LS.mode || (webgl && !saveData && innerWidth >= 900 ? "3d" : "2d") };
  if (!webgl) st.mode = "2d";

  // ---------- разметка ----------
  var opts = groups.map(function (g) { return '<option value="' + esc(g.id) + '">' + esc(g.label) + "</option>"; }).join("");
  ROOT.innerHTML =
    '<div class="ocm-head"><div><span class="kicker">' + esc(T.kicker) + "</span><h2>" + esc(T.title) + '</h2><p class="lede">' + esc(T.lede) + "</p></div>" +
    (groups.length > 1 ? '<label class="ocm-algo" for="ocm-algo">' + esc(T.algo) + '<select id="ocm-algo">' + opts + "</select></label>"
                       : '<span class="ocm-algo1">' + esc(groups[0].label) + "</span>") + "</div>" +
    '<div class="ocm-presets" id="ocm-presets"></div>' +
    '<section class="ocm-stage"><div class="ocm-bar"><p id="ocm-cap"></p><div class="ocm-seg" role="group">' +
    '<button type="button" id="ocm-2d">' + esc(T.simple) + '</button><button type="button" id="ocm-3d">' + esc(T.d3) + "</button></div></div>" +
    '<div id="ocm-plot" class="ocm-plot"></div><div class="ocm-legend" id="ocm-legend"></div></section>' +
    '<details class="ocm-box" open><summary>' + esc(T.table) + ' <span id="ocm-tsub"></span></summary><div class="tw"><table class="ocm-steps" id="ocm-steps"></table></div></details>' +
    '<details class="ocm-box" id="ocm-ownbox"><summary>' + esc(T.own) + " <span>" + esc(T.own_s) + "</span></summary>" +
    '<div class="ocm-own"><div class="ocm-inp"><label for="ocm-core">' + esc(T.core_l) + '<input type="number" id="ocm-core" step="25"></label>' +
    '<label for="ocm-mem">' + esc(T.mem_l) + '<input type="number" id="ocm-mem" step="50"></label>' +
    '<label for="ocm-pl">' + esc(T.pl_l) + '<input type="number" id="ocm-pl" step="5"></label></div><div class="ocm-res" id="ocm-res"></div></div></details>' +
    '<p class="note" id="ocm-foot"></p>';
  var stat = document.querySelectorAll(".ocm-static");
  for (var si = 0; si < stat.length; si++) stat[si].hidden = true;

  // ---------- доход ----------
  var price = {}, cur = LANG === "ru" ? "rub" : "usd", pre = LANG === "ru" ? "" : "$", suf = LANG === "ru" ? " ₽" : "";
  function revenue(h) {
    var net = st.g.net; if (!net || !h) return null;
    var p = price[net.coin];
    if (p === undefined) { price[net.coin] = null; loadPrice(net.coin); return null; }
    return p ? h * net.k * p : null;
  }
  function loadPrice(coin) {
    var go = function () {
      if (typeof OCBotRevenue === "undefined") return setTimeout(go, 300);
      OCBotRevenue.resolvePrices([coin], cur).then(function (m) { price[coin] = m && m[coin] ? m[coin] : 0; renderPresets(); renderOwn(false); });
    };
    go();
  }

  // ---------- пресеты ----------
  var PCOL = { eco: "--ocm-eco", rec: "--accent", max: "--ocm-max" };
  function renderPresets() {
    var A = st.g.A, m = A.max, box = $("ocm-presets"); box.innerHTML = "";
    A.presets.forEach(function (p) {
      var el = document.createElement("div");
      el.className = "ocm-pc " + p.id; el.tabIndex = 0; el.setAttribute("role", "button"); el.setAttribute("aria-pressed", st.sel === p.id);
      var dh = (p.h / m.h - 1) * 100, dw = (p.w / m.w - 1) * 100, pct = p.tested ? Math.round(p.holds / p.tested * 100) : 0, rv = revenue(p.h);
      el.innerHTML = '<div class="ocm-tag"><i></i>' + esc(T[p.id]) + (p.id === "rec" ? '<span class="badge">' + esc(T.best) + "</span>" : "") + "</div>" +
        '<div class="h">' + fmt(p.h, 1) + "<small>" + esc(UNIT) + "</small></div>" +
        '<div class="sub">' + fmt(p.w, 0) + " " + T.w + " · " + fmt(p.eff, 3) + " " + esc(T.per_w) + "</div>" +
        (rv ? '<div class="rev" title="' + esc(T.rev_note) + '">≈ ' + pre + fmt(rv, 2) + suf + T.day + "</div>" : "") +
        '<div class="vs">' + (p.id === "max" ? esc(T.vs_max) : fill(esc(T.vs), { h: "<b>" + fmt(dh, 0) + "</b>", w: "<b>" + fmt(dw, 0) + "</b>" })) + "</div>" +
        '<div class="oc"><div><span>' + T.core + "</span><b>" + sgn(p.core) + "</b></div><div><span>" + T.mem + "</span><b>" + sgn(p.mem) + "</b></div><div><span>" + T.pl + "</span><b>" + p.pl + " " + T.w + "</b></div></div>" +
        '<div class="pfoot"><span class="hold">' + fill(T.hold, { a: p.holds, b: p.tested }) + '<em style="--p:' + pct + '%"></em></span><button type="button" class="copy">' + esc(T.copy) + "</button></div>";
      var pick = function () { st.sel = p.id; setOwn(p); renderPresets(); draw(); };
      el.addEventListener("click", function (ev) { if (!ev.target.closest(".copy")) pick(); });
      el.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); } });
      var cb = el.querySelector(".copy");
      cb.addEventListener("click", function () {
        var t = "Core " + sgn(p.core) + "  Mem " + sgn(p.mem) + "  PL " + p.pl;
        var done = function () { cb.textContent = T.copied; setTimeout(function () { cb.textContent = T.copy; }, 1600); };
        try { navigator.clipboard.writeText(t).then(done, function () { cb.textContent = t; }); } catch (e) { cb.textContent = t; }
      });
      box.appendChild(el);
    });
  }

  // ---------- таблица ----------
  function renderSteps() {
    var g = st.g, A = g.A, pts = g.P, good = pts.filter(function (q) { return q.kind === "ok"; });
    var cores = Array.from(new Set(pts.map(function (q) { return q.core; }))).sort(function (a, b) { return a - b; }), rows = "";
    cores.forEach(function (C) {
      var at = good.filter(function (q) { return q.core === C; }), crs = pts.filter(function (q) { return q.core === C && q.kind === "crash"; });
      var ps = A.presets.filter(function (p) { return p.core === C; });
      var p = ps.filter(function (x) { return x.id === "rec"; })[0] || ps.filter(function (x) { return x.id === "eco"; })[0] || ps[0];
      var top = function (list) { return list.reduce(function (a, b) { return !a || b.h > a.h ? b : a; }, null); };
      var best = p || top(A.ok.filter(function (c) { return c.core === C; }));
      var any = best || top(A.cand.filter(function (c) { return c.core === C; }));
      var hs = at.map(function (q) { return q.h; });
      var r = any ? { holds: any.holds, tested: any.tested } : { holds: 0, tested: new Set(crs.map(function (q) { return q.card; })).size };
      var pct = r.tested ? Math.round(r.holds / r.tested * 100) : 0;
      var cls = (p ? "pr " + p.id : "") + (best ? "" : " bad");
      var tag = p ? ps.map(function (x) { return '<span class="pn ' + x.id + '"><i></i>' + esc(T[x.id]) + (x !== p ? " · " + x.pl + " " + T.w : "") + "</span>"; }).join(" ") : best ? "" : crs.length ? '<span class="crash">' + esc(T.crash) + "</span>" : '<span class="rng">' + esc(T.few) + "</span>";
      rows += '<tr class="' + cls + '"><td>' + sgn(C) + "</td>" +
        (any ? "<td>" + sgn(any.mem) + "</td><td>" + any.pl + " " + T.w + "</td><td><b>" + fmt(any.h, 1) + "</b></td>" : "<td>—</td><td>—</td><td>—</td>") +
        '<td class="rng">' + (hs.length ? fmt(Math.min.apply(null, hs), 1) + "–" + fmt(Math.max.apply(null, hs), 1) : "—") + "</td>" +
        "<td>" + (any ? fmt(any.w, 0) : "—") + "</td>" +
        "<td>" + r.holds + " / " + r.tested +
        '<span class="bar5' + (pct < 75 ? " warn" : "") + '" style="--p:' + pct + '%"></span></td><td>' + tag + "</td></tr>";
    });
    $("ocm-steps").innerHTML = "<thead><tr>" + T.th.map(function (h) { return "<th>" + esc(h) + "</th>"; }).join("") + "</tr></thead><tbody>" + rows + "</tbody>";
    $("ocm-tsub").textContent = fill(T.tsub, { a: sgn(cores[0]), b: sgn(cores[cores.length - 1]) });
  }

  // ---------- простой график (SVG) ----------
  function nice(lo, hi, n) {
    var span = hi - lo || 1, step = Math.pow(10, Math.floor(Math.log10(span / n))), err = span / n / step;
    step *= err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
    var out = []; for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }
  function draw2d() {
    var A = st.g.A, good = st.g.P.filter(function (q) { return q.kind === "ok" && q.w != null; });
    var box = $("ocm-plot"), W = Math.max(320, Math.round(box.clientWidth || 760)), H = W < 600 ? 300 : 380, L = W < 600 ? 44 : 56, R = 16, TT = 22, B = 46;
    box.style.height = H + "px";
    var xs = good.map(function (q) { return q.w; }).concat(A.presets.map(function (p) { return p.w; }));
    var ys = good.map(function (q) { return q.h; }).concat(A.presets.map(function (p) { return p.h; }));
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var px = (x1 - x0) * 0.05 || 5, py = (y1 - y0) * 0.08 || 2; x0 -= px; x1 += px; y0 -= py; y1 += py;
    var X = function (v) { return L + (W - L - R) * (v - x0) / (x1 - x0); }, Y = function (v) { return TT + (H - TT - B) * (1 - (v - y0) / (y1 - y0)); };
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(T.y2 + " / " + T.x2) + '">';
    nice(y0, y1, 5).forEach(function (v) { s += '<line class="g" x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '"/><text class="t" x="' + (L - 8) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end">' + fmt(v, 0) + "</text>"; });
    nice(x0, x1, 6).forEach(function (v) { s += '<text class="t" x="' + X(v).toFixed(1) + '" y="' + (H - B + 18) + '" text-anchor="middle">' + fmt(v, 0) + "</text>"; });
    s += '<text class="a" x="' + (L + (W - L - R) / 2) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(T.x2) + '</text><text class="a" transform="translate(14 ' + (TT + (H - TT - B) / 2) + ') rotate(-90)" text-anchor="middle">' + esc(T.y2) + "</text>";
    good.forEach(function (q) { s += '<circle class="p" cx="' + X(q.w).toFixed(1) + '" cy="' + Y(q.h).toFixed(1) + '" r="3.6"><title>' + esc(D.model) + " №" + (q.card + 1) + ": core " + sgn(q.core) + ", mem " + sgn(q.mem) + ", PL " + q.pl + " — " + fmt(q.h, 1) + " " + esc(UNIT) + ", " + fmt(q.w, 0) + " " + T.w + "</title></circle>"; });
    if (A.frontier.length > 1) s += '<polyline class="f" points="' + A.frontier.map(function (c) { return X(c.w).toFixed(1) + "," + Y(c.h).toFixed(1); }).join(" ") + '"/>';
    var anchor = { eco: ["start", 12, 18], rec: ["middle", 0, -16], max: ["end", -12, -14] }, edge = W < 600 ? 90 : 150;
    A.presets.forEach(function (p) {
      var a = anchor[p.id], x = X(p.w), y = Y(p.h), on = st.sel === p.id;
      var ta = a[0]; if (ta !== "end" && x > W - edge) ta = "end"; if (ta !== "start" && x < L + edge) ta = "start";
      s += '<g class="ps ' + p.id + '"><circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (on ? 10 : 8) + '"><title>' + esc(T[p.id]) + ": core " + sgn(p.core) + ", mem " + sgn(p.mem) + ", PL " + p.pl + "</title></circle>" +
        '<text x="' + (x + (ta === "end" ? -12 : ta === "start" ? 12 : 0)).toFixed(1) + '" y="' + Math.max(TT + 12, Math.min(H - B - 6, y + a[2])).toFixed(1) + '" text-anchor="' + ta + '">' + esc(T[p.id]) + "</text></g>";
    });
    if (st.own && st.own.h) s += '<path class="me" d="M' + X(st.own.w).toFixed(1) + " " + (Y(st.own.h) - 9).toFixed(1) + "l9 9-9 9-9-9z" + '"><title>' + esc(T.your) + "</title></path>";
    $("ocm-plot").innerHTML = s + "</svg>";
  }

  // ---------- 3D (Plotly gl3d с самого сайта, грузится по требованию) ----------
  var plotlyState = 0, cam = null;
  function withPlotly(cb) {
    if (window.Plotly) return cb();
    if (plotlyState === 2) return;
    $("ocm-plot").innerHTML = '<p class="ocm-wait">' + esc(T.loading) + "</p>";
    if (plotlyState === 1) return;
    plotlyState = 1;
    var s = document.createElement("script"); s.src = "assets/plotly-gl3d.min.js"; s.async = true;
    s.onload = function () { plotlyState = 3; draw(); };
    s.onerror = function () { plotlyState = 2; st.mode = "2d"; draw(); $("ocm-cap").textContent = T.no3d; };
    document.head.appendChild(s);
  }
  function surface(good) {
    var xs = [], ys = [], c = good.map(function (q) { return q.core; }), p = good.map(function (q) { return q.pl; });
    for (var x = Math.min.apply(null, c); x <= Math.max.apply(null, c); x += 12.5) xs.push(x);
    for (var y = Math.min.apply(null, p); y <= Math.max.apply(null, p); y += 5) ys.push(y);
    return { xs: xs, ys: ys, z: ys.map(function (y) { return xs.map(function (x) { var e = estimate(good, x, y); return e.dist <= 1.5 ? +e.h.toFixed(2) : null; }); }) };
  }
  function draw3d() {
    var g = st.g, good = g.P.filter(function (q) { return q.kind === "ok"; }), cr = g.P.filter(function (q) { return q.kind === "crash"; });
    var t = { fg: css("--ink"), muted: css("--muted"), line: css("--line"), acc: css("--accent"), soft: css("--accent-soft"), crash: css("--neg"), panel: css("--surface"),
              eco: css("--ocm-eco"), max: css("--ocm-max"), fn: css("--font-ui"), fm: css("--font-num") };
    if (!g._s) g._s = surface(good);
    var col = { eco: t.eco, rec: t.acc, max: t.max }, tr = [];
    tr.push({ type: "surface", x: g._s.xs, y: g._s.ys, z: g._s.z, opacity: 0.85, showscale: false, colorscale: [[0, t.soft], [1, t.acc]],
      contours: { z: { show: true, usecolormap: false, color: t.panel, width: 1 } }, lighting: { ambient: 0.85, diffuse: 0.4, specular: 0.05 },
      hovertemplate: "core %{x:+} · PL %{y} " + T.w + "<br><b>≈ %{z:.1f} " + UNIT + "</b><extra></extra>" });
    tr.push({ type: "scatter3d", mode: "markers", x: good.map(function (q) { return q.core; }), y: good.map(function (q) { return q.pl; }), z: good.map(function (q) { return q.h; }),
      marker: { size: 2.6, color: t.muted, opacity: 0.75 }, customdata: good.map(function (q) { return [D.model + " №" + (q.card + 1), sgn(q.mem), q.w == null ? "—" : Math.round(q.w)]; }),
      hovertemplate: "%{customdata[0]}<br>core %{x:+} · mem %{customdata[1]} · PL %{y}<br><b>%{z:.1f} " + UNIT + "</b> · %{customdata[2]} " + T.w + "<extra>" + T.measured + "</extra>" });
    if (cr.length) tr.push({ type: "scatter3d", mode: "markers", x: cr.map(function (q) { return q.core; }), y: cr.map(function (q) { return q.pl; }),
      z: cr.map(function (q) { return estimate(good, q.core, q.pl).h; }), marker: { size: 4, symbol: "diamond", color: t.crash },
      customdata: cr.map(function (q) { return [D.model + " №" + (q.card + 1), sgn(q.mem)]; }), hovertemplate: "<b>" + T.lg_crash + "</b> · %{customdata[0]}<br>core %{x:+} · mem %{customdata[1]} · PL %{y}<extra></extra>" });
    g.A.presets.forEach(function (p) {
      tr.push({ type: "scatter3d", mode: "markers+text", x: [p.core], y: [p.pl], z: [p.h + 0.6], text: [T[p.id]], textposition: "top center",
        textfont: { family: t.fn, size: 13, color: col[p.id] }, marker: { size: st.sel === p.id ? 9 : 7, color: col[p.id], line: { color: t.panel, width: 2 } },
        hovertemplate: "<b>" + T[p.id] + "</b><br>core " + sgn(p.core) + " · mem " + sgn(p.mem) + " · PL " + p.pl + "<br>" + fmt(p.h, 1) + " " + UNIT + "<extra></extra>" });
    });
    if (st.own && st.own.h) tr.push({ type: "scatter3d", mode: "markers", x: [st.own.core], y: [st.own.pl], z: [st.own.h], marker: { size: 8, symbol: "diamond", color: t.panel, line: { color: t.fg, width: 2 } }, hovertemplate: T.your + " · %{z:.1f}<extra></extra>" });
    var ax = function (x) { return { title: { text: x, font: { size: 12, color: t.muted } }, gridcolor: t.line, zerolinecolor: t.line, showbackground: false, tickfont: { size: 10, color: t.muted, family: t.fm }, showspikes: false }; };
    var lay = { paper_bgcolor: "rgba(0,0,0,0)", margin: { l: 0, r: 0, t: 0, b: 0 }, showlegend: false, font: { family: t.fn, color: t.fg },
      hoverlabel: { bgcolor: t.panel, bordercolor: t.line, font: { family: t.fm, size: 12, color: t.fg } },
      scene: { xaxis: ax(T.x3), yaxis: ax(T.y3), zaxis: ax(UNIT), camera: cam || { eye: { x: 1.5, y: -1.6, z: 0.8 } }, aspectmode: "manual", aspectratio: { x: 1.25, y: 1.1, z: 0.7 } } };
    var el = $("ocm-plot");
    if (!el._pl) { el.innerHTML = ""; el._pl = 1; }
    Plotly.react(el, tr, lay, { displaylogo: false, responsive: true, displayModeBar: false });
    if (!el._hook) { el._hook = 1; el.on("plotly_relayout", function (e) { if (e["scene.camera"]) cam = e["scene.camera"]; }); }
  }
  function draw() {
    var is3 = st.mode === "3d";
    $("ocm-2d").setAttribute("aria-pressed", !is3); $("ocm-3d").setAttribute("aria-pressed", is3);
    $("ocm-cap").textContent = is3 ? T.cap3 : T.cap2;
    $("ocm-legend").innerHTML = is3
      ? '<span><i class="lg sf"></i>' + esc(T.lg_surf) + '</span><span><i class="lg"></i>' + esc(T.lg_pt) + '</span><span><i class="lg cr"></i>' + esc(T.lg_crash) + "</span>"
      : '<span><i class="lg"></i>' + esc(T.lg_pt) + '</span><span><i class="lg line"></i>' + esc(T.lg_line) + "</span>";
    var el = $("ocm-plot");
    if (is3) { el.style.height = ""; return withPlotly(draw3d); }
    if (el._pl && window.Plotly) { Plotly.purge(el); el._pl = 0; el._hook = 0; }
    draw2d();
  }
  var rsz = null, lastW = 0;
  window.addEventListener("resize", function () {
    clearTimeout(rsz);
    rsz = setTimeout(function () { var w = $("ocm-plot").clientWidth; if (st.mode === "2d" && Math.abs(w - lastW) > 20) { lastW = w; draw2d(); } }, 150);
  });
  function setMode(m) {
    if (m === "3d" && !webgl) return;
    st.mode = m; LS.mode = m; save(); draw();
  }
  $("ocm-2d").onclick = function () { setMode("2d"); };
  $("ocm-3d").onclick = function () { setMode("3d"); };
  if (!webgl) $("ocm-3d").disabled = true;

  // ---------- свой разгон ----------
  function setOwn(p) { $("ocm-core").value = p.core; $("ocm-mem").value = p.mem; $("ocm-pl").value = p.pl; renderOwn(false); }
  function renderOwn(mark) {
    var core = +$("ocm-core").value || 0, mem = +$("ocm-mem").value || 0, pl = +$("ocm-pl").value || 0;
    var pts = st.g.P, good = pts.filter(function (q) { return q.kind === "ok"; }), e = estimate(good, core, pl, mem), r = reliability(pts, core, pl);
    var far = e.dist > 2, w = e.w == null ? null : Math.min(e.w, pl), m = st.g.A.max;
    if (mark) { st.own = far ? null : { core: core, pl: pl, h: e.h, w: w }; st.sel = null; }
    var v = far ? '<p class="crash">' + esc(T.far) + "</p>" : !r.tested ? "<p>" + esc(T.nodirect) + "</p>"
      : r.holds === r.tested ? '<p class="good">' + fill(esc(T.all_ok), r2(r)) + "</p>" : "<p>" + fill(esc(T.some), r2(r)) + "</p>";
    var rv = far ? null : revenue(e.h);
    $("ocm-res").innerHTML = '<div class="big">' + (far ? "—" : fmt(e.h, 1)) + " <small>" + esc(UNIT) + " · " + (far || w == null ? "—" : fmt(w, 0)) + " " + T.w +
      (rv ? " · ≈ " + pre + fmt(rv, 2) + suf + T.day : "") + "</small></div>" + v +
      (!far && m ? '<p class="muted">' + fill(esc(T.cmp), { h: fmt((e.h / m.h - 1) * 100, 0), w: fmt((w / m.w - 1) * 100, 0) }) + "</p>" : "");
  }
  function r2(r) { return { a: r.holds, b: r.tested }; }
  ["ocm-core", "ocm-mem", "ocm-pl"].forEach(function (id) { $(id).addEventListener("input", function () { renderOwn(true); renderPresets(); draw(); }); });

  // ---------- запуск ----------
  function selectGroup(g) {
    st.g = g; st.sel = "rec"; st.own = null; cam = null;
    var sel = $("ocm-algo"); if (sel) sel.value = g.id;
    var rec = g.A.presets.filter(function (p) { return p.id === "rec"; })[0]; if (rec) setOwn(rec);
    var b = g.boards ? Object.keys(g.boards).map(function (k) { return k + (g.boards[k] > 1 ? " ×" + g.boards[k] : ""); }).join(", ") : "";
    $("ocm-foot").textContent = fill(T.cards_from, { n: g.cards, cw: cw(g.cards), model: D.model, b: b ? " (" + b + ")" : "" });
    renderPresets(); renderSteps(); draw();
  }
  var selEl = $("ocm-algo");
  if (selEl) selEl.addEventListener("change", function () { LS.g = selEl.value; save(); selectGroup(groups.filter(function (g) { return g.id === selEl.value; })[0]); });
  selectGroup(st.g);
  var rerender = function () { renderPresets(); draw(); };
  try {
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rerender);
    new MutationObserver(rerender).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  } catch (e) { /* старый браузер */ }
})();
