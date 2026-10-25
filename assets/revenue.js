/* Общий модуль получения курса монеты для расчёта дохода: используется главной, каталогом и
 * страницами моделей (сначала показывает последнюю известную цену из кэша, затем обновляет её).
 *
 * Слои резерва, по порядку:
 * 1) Воркер ocbot-catalog (/price.json) — тот же источник, с которого страница уже получает
 *    catalog.json/coinmap.json, то есть точно доступен ей сейчас. Сам воркер внутри тоже пробует
 *    CoinGecko → Gate.io → свой кэш в KV, так что это резерв и для случая, когда у посетителя
 *    (например, из-за мобильного оператора) заблокирован прямой доступ к CoinGecko/Gate.io.
 * 2) CoinGecko прямо из браузера посетителя.
 * 3) Gate.io прямо из браузера посетителя (пары проверены вручную — см. GATE_PAIR).
 * 4) Последняя успешно полученная цена из localStorage (до 7 дней), чтобы не прятать строку дохода
 *    совсем, даже если все источники сейчас недоступны.
 */
(function (global) {
  "use strict";
  var GECKO = "https://api.coingecko.com/api/v3";
  var COMMUNITY_URL = "https://ocbot-catalog.ocbotauto.workers.dev";
  // Тикеры, где символ в CoinGecko не совпадает с ожидаемым id.
  var COIN_ID_OVERRIDE = { PRL: "pearl-2" };
  // Пары Gate.io проверены вручную: "PRL_USDT" на Gate — это другой, не связанный токен;
  // нужная монета Pearl лежит в "PEARL_USDT". Для новых тикеров добавлять только после ручной проверки.
  var GATE_PAIR = { PRL: "PEARL_USDT" };

  function grabJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function geckoList() {
    try {
      var c = JSON.parse(localStorage.getItem("ocbot-gecko-list") || "null");
      if (c && Date.now() - c.t < 24 * 3600 * 1000) return Promise.resolve(c.list);
    } catch (e) {}
    return grabJson(GECKO + "/coins/list").then(function (list) {
      try { localStorage.setItem("ocbot-gecko-list", JSON.stringify({ t: Date.now(), list: list })); } catch (e) {}
      return list;
    }).catch(function () { return []; });
  }

  function resolveCoinIds(tickers, list) {
    var bySymbol = {};
    (list || []).forEach(function (c) {
      var s = (c.symbol || "").toUpperCase();
      if (!(s in bySymbol)) bySymbol[s] = c.id;
    });
    var out = {};
    tickers.forEach(function (t) { out[t] = COIN_ID_OVERRIDE[t] || bySymbol[t] || null; });
    return out;
  }

  function readCache(cur, ticker) {
    try {
      var c = JSON.parse(localStorage.getItem("ocbot-price-cache-" + cur) || "null");
      var p = c && c[ticker];
      if (p && Date.now() - p.t < 7 * 24 * 3600 * 1000) return p.v;
    } catch (e) {}
    return null;
  }

  function writeCache(cur, ticker, v) {
    try {
      var c = JSON.parse(localStorage.getItem("ocbot-price-cache-" + cur) || "null") || {};
      c[ticker] = { v: v, t: Date.now() };
      localStorage.setItem("ocbot-price-cache-" + cur, JSON.stringify(c));
    } catch (e) {}
  }

  function workerPrices(tickers, cur) {
    if (!tickers.length) return Promise.resolve({});
    return grabJson(COMMUNITY_URL + "/price.json?tickers=" + tickers.join(",")).then(function (d) {
      var out = {};
      tickers.forEach(function (t) {
        var p = d && d.prices && d.prices[t];
        out[t] = p && p[cur] != null ? p[cur] : null;
      });
      return out;
    }).catch(function () { return {}; });
  }

  function geckoPrices(tickers, cur) {
    if (!tickers.length) return Promise.resolve({});
    return geckoList().then(function (list) {
      var ids = resolveCoinIds(tickers, list);
      var idList = Array.from(new Set(Object.values(ids).filter(Boolean)));
      if (!idList.length) return {};
      return grabJson(GECKO + "/simple/price?ids=" + idList.join(",") + "&vs_currencies=" + cur).then(function (prices) {
        var out = {};
        tickers.forEach(function (t) {
          var id = ids[t];
          out[t] = id && prices[id] ? prices[id][cur] : null;
        });
        return out;
      }).catch(function () { return {}; });
    });
  }

  function usdFx(toCur) {
    if (toCur === "usd") return Promise.resolve(1);
    try {
      var c = JSON.parse(localStorage.getItem("ocbot-fx-usd") || "null");
      if (c && Date.now() - c.t < 24 * 3600 * 1000 && c.rates && c.rates[toCur.toUpperCase()]) {
        return Promise.resolve(c.rates[toCur.toUpperCase()]);
      }
    } catch (e) {}
    return grabJson("https://open.er-api.com/v6/latest/USD").then(function (d) {
      if (d && d.rates) { try { localStorage.setItem("ocbot-fx-usd", JSON.stringify({ t: Date.now(), rates: d.rates })); } catch (e) {} }
      return (d && d.rates && d.rates[toCur.toUpperCase()]) || null;
    }).catch(function () { return null; });
  }

  function gatePrices(tickers, cur) {
    var usable = tickers.filter(function (t) { return GATE_PAIR[t]; });
    if (!usable.length) return Promise.resolve({});
    return usdFx(cur).then(function (fx) {
      return Promise.all(usable.map(function (t) {
        return grabJson("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=" + GATE_PAIR[t]).then(function (arr) {
          var p = arr && arr[0] && parseFloat(arr[0].last);
          return (p > 0 && fx) ? p * fx : null;
        }).catch(function () { return null; });
      })).then(function (vals) {
        var out = {};
        usable.forEach(function (t, i) { out[t] = vals[i]; });
        return out;
      });
    });
  }

  // Возвращает { TICKER: цена_в_cur | null } для списка тикеров. cur — "usd" | "eur" | "rub".
  function resolvePrices(tickers, cur) {
    tickers = Array.from(new Set((tickers || []).filter(Boolean)));
    if (!tickers.length) return Promise.resolve({});
    return workerPrices(tickers, cur).then(function (fromWorker) {
      var missing = tickers.filter(function (t) { return fromWorker[t] == null; });
      if (!missing.length) return fromWorker;
      return geckoPrices(missing, cur).then(function (fromGecko) {
        var merged = Object.assign({}, fromWorker, fromGecko);
        var stillMissing = tickers.filter(function (t) { return merged[t] == null; });
        if (!stillMissing.length) return merged;
        return gatePrices(stillMissing, cur).then(function (fromGate) {
          stillMissing.forEach(function (t) { if (fromGate[t] != null) merged[t] = fromGate[t]; });
          return merged;
        });
      });
    }).then(function (priceByCoin) {
      tickers.forEach(function (t) {
        if (priceByCoin[t] != null) writeCache(cur, t, priceByCoin[t]);
        else priceByCoin[t] = readCache(cur, t);
      });
      return priceByCoin;
    });
  }

  global.OCBotRevenue = { resolvePrices: resolvePrices };
})(window);
