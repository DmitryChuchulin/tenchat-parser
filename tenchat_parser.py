#!/usr/bin/env python3
"""Парсер постов TenChat по хештегам через DOM-разметку карточек."""
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
from bs4 import BeautifulSoup

BASE_URL = "https://tenchat.ru"
HASHTAG_URL = BASE_URL + "/hashtag/{tag}"
TIMEOUT = 20
MIN_DELAY = 2.0
MAX_DELAY = 3.0

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
    "razrabotka", "itrazrabotka", "veb", "webrazrabotka", "razrabotkasaytov",
    "mobilnoyeprilozheniye", "razrabotkaprilozheniy", "erp", "crm", "avtomatizatsiya",
    "tsifrovizatsiya", "biznesprotsessy", "autsorsing", "autstaffing", "cto",
    "itdirektor", "predprinimatel", "osnovatel", "startap", "mvp",
    "tender", "upravleniyeproyektami", "ii", "neyroseti", "arkhitektura",
    "fintekh", "development", "biznes", "delovyyesvyazi", "sotrudnichestvo",
]

CSV_FIELDS = ["title", "author", "date", "url", "views", "hashtag"]

# Формат счётчика просмотров: "1234", "2.7K", "185.3K", "1,2 M", "1.2M"
VIEWS_RE = re.compile(r"^\d+([.,]\d+)?\s*[KMkmКМкмТтТЫСтыс]*$")


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
        # Автор — второй блок, если он не похож на счётчик просмотров
        author = ""
        if len(texts) >= 2 and not VIEWS_RE.match(texts[1]):
            author = texts[1]
        # Просмотры — последний блок, подходящий под формат счётчика
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


def collect(tags: list[str]) -> list[Post]:
    seen: dict[str, Post] = {}
    session = requests.Session()
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


def save_csv(posts: list[Post], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for p in posts:
            writer.writerow(asdict(p))


def main() -> int:
    ap = argparse.ArgumentParser(description="TenChat hashtag parser")
    ap.add_argument(
        "--tags",
        nargs="+",
        default=HASHTAGS,
        help="Список хештегов (по умолчанию — полный HASHTAGS).",
    )
    args = ap.parse_args()

    posts = collect(list(args.tags))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"posts_{ts}.csv")
    save_csv(posts, out)
    print(f"\nГотово. Уникальных постов: {len(posts)}")
    print(f"Файл: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
