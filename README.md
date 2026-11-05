# ocbot.org — сайт проекта OCBot

Исходники сайта **[ocbot.org](https://ocbot.org)** — статический сайт на GitHub Pages, RU + EN версии.

[![Сайт](https://img.shields.io/badge/site-ocbot.org-2ea44f)](https://ocbot.org)
[![Telegram-канал](https://img.shields.io/badge/telegram-%40ocbot__auto-26A5E4)](https://t.me/ocbot_auto)

## Что на сайте

- **Гайд по установке** — одна команда, мастер сам находит карты и майнер: [guide.ru.html](https://ocbot.org/guide.ru.html)
- **Каталог пресетов** — проверенные пресеты разгона с живых ригов: модель карты, память, хешрейт, ватты, эффективность: [catalog.ru.html](https://ocbot.org/catalog.ru.html)
- **Калькулятор дохода** — с учётом вашей цены электричества: [calculator.ru.html](https://ocbot.org/calculator.ru.html)
- **Статьи** — эксплуатация фермы без воды: свет, железо, доходность
- **Чат-помощник** — ответы по установке, командам, лицензии (воркер `ocbot-support`)

## Структура

- `*.html` / `*.ru.html` — страницы (EN / RU)
- `chat.js`, `chat.en.js` — виджет чата поддержки
- `.github/workflows/` — автосборка страниц моделей из каталога и деплой на Pages

## Связанные репозитории

- **[ocbotauto/ocbot-dist](https://github.com/ocbotauto/ocbot-dist)** — защищённые сборки бота и верификация

Исходный код бота закрыт; здесь только сайт. Вопросы: [@OCBotSupport_bot](https://t.me/OCBotSupport_bot).
