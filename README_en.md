# TenChat Parser + vc.ru

Daily parser for TenChat hashtag posts and vc.ru articles.  
Goal: find fresh content for expert commenting on behalf of Elgrow.

---

## What it does

- Parses **57 hashtags** on TenChat (transliterated, e.g. `razrabotka`, `crm`, `iivbiznese`)
- Parses **15 sections** on vc.ru (ai, marketing, dev, services, etc.)
- Filters posts by date (not older than 2 days)
- Filters vc.ru articles by views (≥ 1000)
- Appends results to Google Sheets without duplicates
- Sends a Telegram notification when done

---

## File structure

```
tenchat-parser/
├── tenchat_parser.py      # Main TenChat parser script
├── vc_parser.py           # vc.ru parser
├── sheets_writer.py       # Google Sheets writer
├── requirements.txt       # Python dependencies
├── .env                   # Secrets (not in git)
└── .github/
    └── workflows/
        └── daily_parse.yml  # GitHub Actions (disabled, server cron is used instead)
```

---

## How TenChat parser works

**Step 1:** Crawls hashtag pages `https://tenchat.ru/hashtag/{tag}`, collects post links via DOM parsing of `/media/` links. Collects ~600+ unique posts.

**Step 2:** Visits each post, extracts the date from JSON-LD (`datePublished`), filters by `--cutoff-date`.

Total run time: ~40-50 minutes, yields ~10-20 posts from the last 2 days.

---

## How vc.ru parser works

Parses two URLs per section (`/ai` and `/ai/new`). Date and view count are extracted directly from the listing HTML — no separate requests per article needed. Run time: ~1 minute.

---

## Google Sheets

| Spreadsheet | ID | Sheet |
|---|---|---|
| Tenchat Posts | `1Vk7jOLmw1O_vuNEzQcTDarEzXv1Yy4eO90IsA5rhSUM` | `posts` |
| Tenchat Posts | `1Vk7jOLmw1O_vuNEzQcTDarEzXv1Yy4eO90IsA5rhSUM` | `vc.ru` |

TenChat columns: `Title | Author | Date | URL | Views | Hashtag`  
vc.ru columns: `Title | Author | Date | URL | Views | Section`

---

## Environment variables (.env)

```env
GOOGLE_SHEET_ID=1Vk7jOLmw1O_vuNEzQcTDarEzXv1Yy4eO90IsA5rhSUM
GOOGLE_CREDENTIALS_JSON=/opt/service-account.json
TELEGRAM_BOT_TOKEN=<@ElgrowsBot token>
TELEGRAM_CHAT_ID=<Dmitry's chat_id>
```

`GOOGLE_CREDENTIALS_JSON` — path to Google Service Account JSON file **or** JSON content as a string.

---

## Manual run

```bash
# Load environment variables
cd /opt/tenchat-parser
set -a && source .env && set +a

# TenChat parser (full run)
.venv/bin/python tenchat_parser.py --cutoff-date 2026-04-24 --sheets

# TenChat parser (quick check, skip date enrichment)
.venv/bin/python tenchat_parser.py --cutoff-date 2026-04-24 --no-enrich --sheets

# vc.ru parser
.venv/bin/python vc_parser.py --cutoff-date 2026-04-24 --sheets
```

---

## Server schedule (cron)

Server: `213.189.220.225` (netangels VPS)

```
0 4 * * *   TenChat parser     → 07:00 MSK
```

View cron: `crontab -l`  
Edit cron: `crontab -e`

---

## Infrastructure

- **Server:** netangels VPS, Debian 12, 8GB RAM
- **Python:** 3.11, venv at `/opt/tenchat-parser/.venv/`
- **Google:** Service Account `tenchat-parser@tenchat-parser.iam.gserviceaccount.com`
- **Telegram:** bot @ElgrowsBot
- **GitLab:** `https://gitlab.elgrow-ai.ru` (code on GitHub, GitLab migration planned)

---

## Dependencies

```
requests>=2.31
beautifulsoup4>=4.12
gspread>=6.0.0
google-auth>=2.0.0
```

---

## Known limitations

- TenChat only serves top-20 posts per hashtag — not all fresh posts appear in results
- vc.ru only returns ~20 articles per section (pagination is client-side, no API found)
- TenChat run takes ~40 minutes due to request delays (anti-ban protection)
