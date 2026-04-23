#!/usr/bin/env python3
"""Парсер статей vc.ru по разделам."""
from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://vc.ru"
TIMEOUT = 20
MIN_DELAY = 2.0
MAX_DELAY = 3.0
CUTOFF_DATE_DEFAULT = "2026-04-14"
MIN_VIEWS_DEFAULT = 1000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

SECTIONS = [
    "services", "ai", "marketing", "invest", "hr",
    "education", "telegram", "dev", "opinions", "future",
    "design", "growth", "media", "seo", "chatgpt",
]

CSV_FIELDS = ["title", "author", "date", "url", "views", "section"]
SHEET_HEADERS = ["Заголовок", "Автор", "Дата", "URL", "Просмотры", "Раздел"]

ARTICLE_HREF_RE = re.compile(r"^/[A-Za-z0-9_\-]+/\d+-")
VIEWS_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*([KMkmКМкм])?$")


@dataclass
class Article:
    title: str
    author: str
    date: str
    url: str
    views: int
    section: str


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


def parse_view_count(text: str) -> int:
    """'442' → 442, '2.1K' → 2100, '1.5M' → 1500000."""
    if not text:
        return 0
    cleaned = text.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    m = VIEWS_RE.match(cleaned)
    if not m:
        return 0
    value = float(m.group(1))
    suffix = (m.group(2) or "").lower()
    if suffix in ("k", "к"):
        value *= 1000
    elif suffix in ("m", "м"):
        value *= 1_000_000
    return int(value)


def _find_author(card: Tag, article_href: str) -> str:
    """Первая ссылка в шапке, не ведущая на саму статью, с нечисловым текстом."""
    for a in card.find_all("a", href=True):
        if a.find_parent("article"):
            continue
        if a.find_parent(attrs={"class": re.compile(r"content__body")}):
            continue
        if a["href"] == article_href:
            continue
        txt = a.get_text(" ", strip=True)
        if txt and len(txt) > 2 and not txt.replace(".", "").replace(",", "").isdigit():
            return txt
    return ""


def extract_articles(html: str, section: str) -> list[Article]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[Article] = []
    for card in soup.select("div.content.content--short"):
        link = card.find("a", href=ARTICLE_HREF_RE)
        if not link:
            continue
        href = link["href"].split("#")[0]
        url = urljoin(BASE_URL, href)

        title_link = card.select_one("div.content__body a")
        title = title_link.get_text(" ", strip=True) if title_link else ""

        time_el = card.find("time")
        date = (time_el.get("datetime") or "") if time_el else ""

        views_el = card.select_one(".content-stats-item")
        views = parse_view_count(views_el.get_text(strip=True)) if views_el else 0

        articles.append(Article(
            title=title,
            author=_find_author(card, href),
            date=date,
            url=url,
            views=views,
            section=section,
        ))
    return articles


def collect(sections: list[str], session: requests.Session,
            cutoff: str, min_views: int) -> list[Article]:
    seen: dict[str, Article] = {}
    suffixes = ("", "/new")
    total = len(sections) * len(suffixes)
    counter = 0
    for section in sections:
        for suffix in suffixes:
            counter += 1
            url = f"{BASE_URL}/{section}{suffix}"
            print(f"[{counter}/{total}] {url}")
            html = fetch(session, url)
            if html:
                found = extract_articles(html, section)
                kept = 0
                for art in found:
                    day = art.date[:10]
                    if not day or day < cutoff:
                        continue
                    if art.views < min_views:
                        continue
                    if art.url in seen:
                        continue
                    seen[art.url] = art
                    kept += 1
                print(f"    карточек: {len(found)}, прошли фильтр и уникальны: {kept}")
            if counter < total:
                time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    return list(seen.values())


def save_csv(articles: list[Article], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for a in articles:
            writer.writerow(asdict(a))


def main() -> int:
    ap = argparse.ArgumentParser(description="vc.ru section parser")
    ap.add_argument("--cutoff-date", default=CUTOFF_DATE_DEFAULT,
                    help=f"Фильтр: опубликованные не раньше этой даты (YYYY-MM-DD). По умолчанию {CUTOFF_DATE_DEFAULT}.")
    ap.add_argument("--min-views", type=int, default=MIN_VIEWS_DEFAULT,
                    help=f"Фильтр: минимум просмотров. По умолчанию {MIN_VIEWS_DEFAULT}.")
    ap.add_argument("--sheets", action="store_true",
                    help="Дозаписать результат в Google Sheets, вкладка 'vc.ru'.")
    args = ap.parse_args()

    session = requests.Session()
    print(f"=== vc.ru: {len(SECTIONS)} разделов × 2 URL (base + /new) ===")
    articles = collect(SECTIONS, session, args.cutoff_date, args.min_views)
    print(f"\nПосле фильтрации (date>={args.cutoff_date}, views>={args.min_views}): {len(articles)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"vc_{ts}.csv")
    save_csv(articles, out)
    print(f"Файл: {out}")

    if args.sheets:
        import sheets_writer
        added = sheets_writer.write_posts(articles, worksheet_name="vc.ru", headers=SHEET_HEADERS)
        print(f"Google Sheets (vc.ru): добавлено {added} из {len(articles)} (остальное — дубли по URL)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
