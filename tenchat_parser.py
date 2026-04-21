#!/usr/bin/env python3
"""Парсер постов TenChat по хештегам через DOM-разметку карточек."""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tenchat.ru"
HASHTAG_URL = BASE_URL + "/hashtag/{tag}"
TIMEOUT = 20
MIN_DELAY = 2.0
MAX_DELAY = 3.0
CUTOFF_DATE_DEFAULT = "2026-04-14"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

HASHTAGS = [
    "cto", "cio", "tekhdirektor", "itdirektor", "founder",
    "predprinimatel", "startaper", "produktmenedzher", "razrabotka", "webrazrabotka",
    "mobilnayarazrabotka", "backend", "frontend", "devops", "arkhitekturapo",
    "programmirovaniye", "mvp", "startap", "zapuskprodukta", "prototip",
    "techzadaniye", "avtomatizatsiya", "avtomatizatsiyabiznesa", "tsifrovizatsiya", "tsifrovayatransformatsiya",
    "tsifrovoybiznes", "crm", "erp", "iivbiznese", "iskusstvennyintellekt",
    "neyroseti", "analitikadannykh",
    "bigdata", "autstaffing", "autsorsing", "itautstaffing", "razrabotchiki",
    "biznesprotsessy", "masshtabirovaniye", "rostbiznesa", "b2b", "b2bprodazhi",
    "tender", "goszakupki", "zakupki", "fintekh", "korporativnyeresheniya",
    "enterprise",
]

CSV_FIELDS = ["title", "author", "date", "url", "views", "hashtag"]

# Счётчик просмотров: "1234", "2.7K", "185.3K", "1.2M" и т. п.
VIEWS_RE = re.compile(r"^\d+([.,]\d+)?\s*[KMkmКМкмТтТЫСтыс]*$")
LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


@dataclass
class Post:
    title: str
    author: str
    date: str
    url: str
    views: str
    hashtag: str


def fetch(session: requests.Session, url: str) -> str | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code}", file=sys.stderr)
            return None
        return resp.text
    except requests.RequestException as exc:
        print(f"    ошибка запроса: {exc}", file=sys.stderr)
        return None


def extract_posts(html: str, tag: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []
    seen_on_page: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/media/"):
            continue
        url = urljoin(BASE_URL, href)
        if url in seen_on_page:
            continue
        texts = [t.strip() for t in a.stripped_strings if t.strip()]
        if not texts:
            continue
        seen_on_page.add(url)

        title = texts[0]
        author = ""
        if len(texts) >= 2 and not VIEWS_RE.match(texts[1]):
            author = texts[1]
        views = ""
        for t in reversed(texts):
            if VIEWS_RE.match(t):
                views = t
                break

        posts.append(Post(
            title=title,
            author=author,
            date="",
            url=url,
            views=views,
            hashtag=tag,
        ))
    return posts


def extract_date_published(html: str) -> str:
    """Ищет Schema.org datePublished в любом JSON-LD блоке. Возвращает ISO-строку или ''."""
    for block in LD_JSON_RE.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("datePublished"), str):
                return item["datePublished"]
    return ""


def collect(tags: list[str], session: requests.Session) -> list[Post]:
    seen: dict[str, Post] = {}
    for i, tag in enumerate(tags, 1):
        url = HASHTAG_URL.format(tag=tag)
        print(f"[{i}/{len(tags)}] #{tag} → {url}")
        html = fetch(session, url)
        if html:
            found = extract_posts(html, tag)
            new = 0
            for p in found:
                if p.url not in seen:
                    seen[p.url] = p
                    new += 1
            print(f"    постов на странице: {len(found)}, новых: {new}")
        if i < len(tags):
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    return list(seen.values())


def enrich_and_filter(posts: list[Post], session: requests.Session, cutoff: str) -> list[Post]:
    kept: list[Post] = []
    for i, post in enumerate(posts, 1):
        html = fetch(session, post.url)
        if html:
            dp = extract_date_published(html)
            if dp:
                post.date = dp
                day = dp[:10]
                if day >= cutoff:
                    kept.append(post)
                    marker = "+"
                else:
                    marker = "-"
                print(f"  [{i}/{len(posts)}] {marker} {day}  {post.url}")
            else:
                print(f"  [{i}/{len(posts)}] ? нет datePublished  {post.url}")
        if i < len(posts):
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    return kept


def save_csv(posts: list[Post], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for p in posts:
            writer.writerow(asdict(p))


def main() -> int:
    ap = argparse.ArgumentParser(description="TenChat hashtag parser")
    ap.add_argument("--tags", nargs="+", default=HASHTAGS, help="Список хештегов.")
    ap.add_argument("--cutoff-date", default=CUTOFF_DATE_DEFAULT,
                    help=f"Отфильтровать посты опубликованные раньше этой даты (YYYY-MM-DD). По умолчанию {CUTOFF_DATE_DEFAULT}.")
    ap.add_argument("--no-enrich", action="store_true",
                    help="Пропустить шаг дозагрузки даты (даты останутся пустыми, фильтрация не применяется).")
    ap.add_argument("--sheets", action="store_true",
                    help="Дозаписать результат в Google Sheets (требует env GOOGLE_CREDENTIALS_JSON и GOOGLE_SHEET_ID).")
    args = ap.parse_args()

    session = requests.Session()

    print(f"=== Шаг 1: сбор ссылок по {len(args.tags)} тегам ===")
    posts = collect(list(args.tags), session)
    print(f"\nУникальных постов после Шага 1: {len(posts)}")

    if args.no_enrich:
        result = posts
    else:
        print(f"\n=== Шаг 2: дозагрузка даты, фильтр cutoff={args.cutoff_date} ===")
        result = enrich_and_filter(posts, session, args.cutoff_date)
        print(f"\nПосле фильтрации по дате: {len(result)} из {len(posts)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"posts_{ts}.csv")
    save_csv(result, out)
    print(f"\nГотово. В файле: {len(result)}")
    print(f"Файл: {out}")

    if args.sheets:
        import sheets_writer
        added = sheets_writer.write_posts(result)
        print(f"Google Sheets: добавлено {added} из {len(result)} (остальное — дубли по URL)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
