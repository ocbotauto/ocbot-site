// Support chat widget. While SUPPORT_URL is empty, the button is hidden.
(function () {
  var SUPPORT_URL = "";          // support worker address, e.g. https://ocbot-support.xxx.workers.dev
  var TG_LINK = "";              // Telegram support bot link, e.g. https://t.me/xxx_bot
  if (!SUPPORT_URL) return;
  var css = ".ocw-b{position:fixed;right:16px;bottom:16px;z-index:50;padding:12px 16px;border-radius:999px;border:0;background:#0f7a64;color:#fff;font:600 14px system-ui,sans-serif;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.2)}" +
    ".ocw-p{position:fixed;right:16px;bottom:68px;z-index:50;width:min(360px,calc(100vw - 32px));max-height:70vh;display:none;flex-direction:column;background:#fff;color:#16211e;border:1px solid #d6dfdc;border-radius:14px;box-shadow:0 8px 28px rgba(0,0,0,.22);font:14px/1.45 system-ui,sans-serif}" +
    ".ocw-p.on{display:flex}.ocw-l{padding:12px;overflow:auto;flex:1;display:flex;flex-direction:column;gap:8px}" +
    ".ocw-m{padding:8px 10px;border-radius:10px;max-width:92%;white-space:pre-wrap;word-break:break-word}.ocw-m pre{white-space:pre-wrap;background:#eef3f1;padding:6px;border-radius:6px;margin:6px 0 0}" +
    ".ocw-u{align-self:flex-end;background:#0f7a64;color:#fff}.ocw-a{align-self:flex-start;background:#eef3f1}" +
    ".ocw-f{display:flex;gap:6px;padding:10px;border-top:1px solid #d6dfdc}.ocw-f input{flex:1;min-width:0;padding:9px;border:1px solid #c5d0cc;border-radius:8px;font:inherit}.ocw-f button{padding:9px 12px;border:0;border-radius:8px;background:#0f7a64;color:#fff;font:inherit;cursor:pointer}" +
    "@media(prefers-color-scheme:dark){.ocw-p{background:#14201d;color:#e6efec;border-color:#2b3b37}.ocw-a{background:#1f2f2b}.ocw-m pre{background:#0e1816}.ocw-f{border-color:#2b3b37}.ocw-f input{background:#0e1816;color:#e6efec;border-color:#2b3b37}}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  var b = document.createElement("button"); b.className = "ocw-b"; b.type = "button"; b.textContent = "Question about the bot";
  var p = document.createElement("div"); p.className = "ocw-p";
  p.innerHTML = '<div class="ocw-l" role="log" aria-live="polite"></div><form class="ocw-f"><input maxlength="600" placeholder="Ask a question" aria-label="Question"><button type="submit">Send</button></form>';
  document.body.appendChild(p); document.body.appendChild(b);
  var list = p.querySelector(".ocw-l"), form = p.querySelector("form"), inp = p.querySelector("input");
  // from the server's reply, keep only pre/code, escape the rest
  function safe(h) {
    var d = new DOMParser().parseFromString("<body>" + h + "</body>", "text/html").body; var out = document.createElement("div");
    (function walk(n, to) { n.childNodes.forEach(function (c) {
      if (c.nodeType === 3) to.appendChild(document.createTextNode(c.textContent));
      else if (c.nodeType === 1 && (c.tagName === "PRE" || c.tagName === "CODE")) { var e = document.createElement(c.tagName.toLowerCase()); walk(c, e); to.appendChild(e); }
      else if (c.nodeType === 1) walk(c, to);
    }); })(d, out);
    return out;
  }
  function add(cls, node) { var m = document.createElement("div"); m.className = "ocw-m " + cls; m.appendChild(node); list.appendChild(m); list.scrollTop = list.scrollHeight; }
  var t = function (s) { return document.createTextNode(s); };
  add("ocw-a", t("Hello! Ask about installation, commands, keys or payment."));
  b.onclick = function () { p.classList.toggle("on"); if (p.classList.contains("on")) inp.focus(); };
  form.onsubmit = function (e) {
    e.preventDefault(); var q = inp.value.trim(); if (!q) return; inp.value = ""; add("ocw-u", t(q));
    var fail = function () { add("ocw-a", t("The service is currently unavailable." + (TG_LINK ? " Write on Telegram: " + TG_LINK : " Open the guide on the site."))); };
    fetch(SUPPORT_URL.replace(/\/+$/, "") + "/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ q: q }) })
      .then(function (r) { return r.json(); }).then(function (j) { if (j && j.html) add("ocw-a", safe(j.html)); else if (j && j.error === "rate_limited") add("ocw-a", t("Too often, please wait a minute.")); else fail(); }, fail);
  };
})();
