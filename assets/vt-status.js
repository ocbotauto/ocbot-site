/* Подтягивает свежий статус проверки ocbot.zip на VirusTotal (vt-status.json обновляется
   автоматически CI при каждом релизе — см. .github/workflows/verify-protected.yml в ocbot-dist).
   Если файла ещё нет или сеть недоступна — молча оставляем статичный текст/ссылку из HTML. */
(function () {
  var URL = "https://raw.githubusercontent.com/ocbotauto/ocbot-dist/main/vt-status.json";
  function apply(d) {
    if (!d || typeof d.malicious !== "number" || typeof d.total_engines !== "number" || !d.report_url) return;
    var flagged = (d.malicious || 0) + (d.suspicious || 0);
    var label = flagged + "/" + d.total_engines;
    document.querySelectorAll("[data-vt-score]").forEach(function (el) { el.textContent = label; });
    document.querySelectorAll("[data-vt-link]").forEach(function (el) { el.href = d.report_url; });
    if (!d.clean) {
      document.querySelectorAll("[data-vt-warn]").forEach(function (el) { el.style.display = ""; });
    }
  }
  fetch(URL, { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw 0; return r.json(); })
    .then(apply)
    .catch(function () {});
})();
