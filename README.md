# TenChat Parser + vc.ru

Ежедневный парсер постов по хештегам в TenChat и статей на vc.ru.  
Цель — находить свежий контент для экспертных комментариев от лица Elgrow.

---

## Что делает

- Парсит **57 хештегов** в TenChat (транслитом, например `razrabotka`, `crm`, `iivbiznese`)
- Парсит **15 разделов** vc.ru (ai, marketing, dev, services и др.)
- Фильтрует посты по дате (не старше 2 дней)
- Фильтрует статьи vc.ru по просмотрам (≥ 1000)
- Записывает результаты в Google Sheets без дублей
- Шлёт уведомление в Telegram по завершении

---

## Структура файлов

```
tenchat-parser/
├── tenchat_parser.py      # Главный скрипт парсера TenChat
├── vc_parser.py           # Парсер vc.ru
├── sheets_writer.py       # Запись в Google Sheets
├── requirements.txt       # Зависимости Python
├── .env                   # Секреты (не в git)
└── .github/
    └── workflows/
        └── daily_parse.yml  # GitHub Actions (отключён, используется cron на сервере)
```

---

## Как работает TenChat парсер

**Шаг 1:** Обходит страницы хештегов `https://tenchat.ru/hashtag/{tag}`, собирает ссылки на посты через DOM-разбор `/media/` ссылок. Получает ~600+ уникальных постов.

**Шаг 2:** Заходит на каждый пост, достаёт дату из JSON-LD (`datePublished`), фильтрует по `--cutoff-date`.

Итого за прогон: ~40-50 минут, ~10-20 постов за последние 2 дня.

---

## Как работает vc.ru парсер

Парсит два URL на каждый раздел (`/ai` и `/ai/new`), дата и просмотры берутся прямо из HTML листинга — отдельные запросы на каждую статью не нужны. Прогон занимает ~1 минуту.

---

## Google Sheets

| Таблица | ID | Вкладка |
|---|---|---|
| Tenchat Posts | `1Vk7jOLmw1O_vuNEzQcTDarEzXv1Yy4eO90IsA5rhSUM` | `posts` |
| Tenchat Posts | `1Vk7jOLmw1O_vuNEzQcTDarEzXv1Yy4eO90IsA5rhSUM` | `vc.ru` |

Колонки TenChat: `Заголовок | Автор | Дата | URL | Просмотры | Хештег`  
Колонки vc.ru: `Заголовок | Автор | Дата | URL | Просмотры | Раздел`

---

## Переменные окружения (.env)

```env
GOOGLE_SHEET_ID=1Vk7jOLmw1O_vuNEzQcTDarEzXv1Yy4eO90IsA5rhSUM
GOOGLE_CREDENTIALS_JSON=/opt/service-account.json
TELEGRAM_BOT_TOKEN=<токен бота @ElgrowsBot>
TELEGRAM_CHAT_ID=<chat_id Дмитрия>
```

`GOOGLE_CREDENTIALS_JSON` — путь к JSON-файлу Google Service Account **или** сам JSON-контент строкой.

---

## Запуск вручную

```bash
# Активировать переменные окружения
cd /opt/tenchat-parser
set -a && source .env && set +a

# TenChat парсер (полный прогон)
.venv/bin/python tenchat_parser.py --cutoff-date 2026-04-24 --sheets

# TenChat парсер (быстрая проверка без шага 2)
.venv/bin/python tenchat_parser.py --cutoff-date 2026-04-24 --no-enrich --sheets

# vc.ru парсер
.venv/bin/python vc_parser.py --cutoff-date 2026-04-24 --sheets
```

---

## Расписание на сервере (cron)

Сервер: `213.189.220.225` (netangels VPS)

```
0 4 * * *   TenChat парсер     → 07:00 МСК
```

Посмотреть cron: `crontab -l`  
Редактировать: `crontab -e`

---

## Инфраструктура

- **Сервер:** netangels VPS, Debian 12, 8GB RAM
- **Python:** 3.11, venv в `/opt/tenchat-parser/.venv/`
- **Google:** Service Account `tenchat-parser@tenchat-parser.iam.gserviceaccount.com`
- **Telegram:** бот @ElgrowsBot
- **GitLab:** `https://gitlab.elgrow-ai.ru` (код хранится на GitHub, на GitLab — в планах)

---

## Зависимости

```
requests>=2.31
beautifulsoup4>=4.12
gspread>=6.0.0
google-auth>=2.0.0
```

---

## Известные ограничения

- TenChat отдаёт только топ-20 постов на хештег — не все свежие посты попадают в выдачу
- vc.ru отдаёт только ~20 статей на раздел (пагинация клиентская, API не найден)
- Прогон TenChat занимает ~40 минут из-за задержек между запросами (защита от бана)
