import io, glob, re

# ---------- 1) Навигация: добавить ссылку на хаб статей на все страницы ----------
changed_nav = 0
for f in glob.glob("*.html"):
    base = f[:-5]
    if base.startswith(("blog", "status", "stats")):
        continue
    ru = base.endswith(".ru")
    s = io.open(f, encoding="utf-8").read()
    orig = s

    if ru:
        # индексные страницы: убрать мусорную точку и сразу вставить Статьи
        s = s.replace('<a href="security.ru.html">Безопасность</a> · <a href="#"',
                      '<a href="blog.ru.html">Статьи</a><a href="security.ru.html">Безопасность</a><a href="#"', 1)
        if 'blog.ru.html">Статьи</a>' not in s and 'href="security.ru.html">Безопасность</a>' in s:
            s = s.replace('href="security.ru.html">Безопасность</a>',
                          'href="blog.ru.html">Статьи</a>', 1)
            # затем восстановить полный тег для встретившегося вхождения
            s = s.replace('href="blog.ru.html">Статьи</a>',
                          '<a href="blog.ru.html">Статьи</a>', 1)
    else:
        s = s.replace('<a href="security.html">Security</a> · <a href="#"',
                      '<a href="blog.html">Articles</a><a href="security.html">Security</a><a href="#"', 1)
        if 'blog.html">Articles</a>' not in s and 'href="security.html">Security</a>' in s:
            s = s.replace('href="security.html">Security</a>', 'href="blog.html">Articles</a>', 1)
            s = s.replace('href="blog.html">Articles</a>', '<a href="blog.html">Articles</a>', 1)

    if s != orig:
        io.open(f, "w", encoding="utf-8", newline="").write(s)
        changed_nav += 1
print("nav updated on", changed_nav, "pages")

# ---------- 2) индексные футеры: ссылка «Статьи» -> хаб ----------
for f, old, new in [
    ("index.ru.html", '<a href="rig-freezes.ru.html">Статьи</a>', '<a href="blog.ru.html">Статьи</a>'),
    ("index.html", '<a href="rig-freezes.html">Articles</a>', '<a href="blog.html">Articles</a>'),
]:
    s = io.open(f, encoding="utf-8").read()
    n = s.count(old)
    s = s.replace(old, new)
    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print(f, "footer art-link replaced x", n)

# ---------- 3) старые 6 статей: добавить chip «Все статьи» ----------
for f in ["gpu-temps.ru.html", "gpu-temps.html", "psu-budget.ru.html", "psu-budget.html",
          "rig-freezes.ru.html", "rig-freezes.html"]:
    ru = f.endswith(".ru.html")
    s = io.open(f, encoding="utf-8").read()
    label = "Все статьи" if ru else "All articles"
    link = 'blog.ru.html' if ru else 'blog.html'
    if f'<a href="{link}">' in s:
        print(f, "already has blog link"); continue
    i = s.find('<ul class="chips">')
    while i > -1:
        j = s.find('</ul>', i)
        seg = s[i:j]
        if 'calculator' in seg and ('catalog' in seg or 'rig-freezes' in seg):
            s = s[:j] + f'<li><a href="{link}">{label}</a></li>' + s[j:]
            break
        i = s.find('<ul class="chips">', j)
    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print(f, "chip added")

# ---------- 4) sitemap ----------
sm = io.open("sitemap.xml", encoding="utf-8").read()
E = ""
for slug in ("night-off", "fan-health", "manual-vs-auto", "profit-math", "blog"):
    E += (f'\n  <url><loc>https://ocbot.org/{slug}.html</loc>'
          f'<xhtml:link rel="alternate" hreflang="en" href="https://ocbot.org/{slug}.html"/>'
          f'<xhtml:link rel="alternate" hreflang="ru" href="https://ocbot.org/{slug}.ru.html"/></url>'
          f'\n  <url><loc>https://ocbot.org/{slug}.ru.html</loc>'
          f'<xhtml:link rel="alternate" hreflang="en" href="https://ocbot.org/{slug}.html"/>'
          f'<xhtml:link rel="alternate" hreflang="ru" href="https://ocbot.org/{slug}.ru.html"/></url>')
assert "</urlset>" in sm
sm = sm.replace("</urlset>", E + "\n</urlset>")
io.open("sitemap.xml", "w", encoding="utf-8", newline="").write(sm)
print("sitemap locs:", sm.count("<loc>"))

# ---------- 5) контроль парности тегов в новых/изменённых статьях ----------
for f in ["night-off.ru.html","night-off.html","fan-health.ru.html","fan-health.html",
          "manual-vs-auto.ru.html","manual-vs-auto.html","profit-math.ru.html","profit-math.html",
          "blog.ru.html","blog.html"]:
    s = io.open(f, encoding="utf-8").read()
    bad = []
    for tag in ("section","p","ul","ol","li","h2","h3","div"):
        o = len(re.findall('<'+tag+r'[ >\n]', s)); c = s.count('</'+tag+'>')
        if o != c:
            bad.append(f"{tag} {o}/{c}")
    mixed = re.findall(r'[а-яёА-ЯЁ]{2,}[a-zA-Z]{1,4}[а-яёА-ЯЁ]{2,}', s)
    cjk = [hex(ord(c)) for c in set(s) if 0x3000 <= ord(c) <= 0x9fff]
    print(f, "| tags:", bad or "OK", "| mixed:", len(mixed), "| cjk:", len(cjk))
