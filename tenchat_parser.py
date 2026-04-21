#!/usr/bin/env python3
"""Парсер постов TenChat по списку хештегов."""
from __future__ import annotations

import csv
import random
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


HASHTAGS: list[str] = [
    "разработка", "itразработка", "веб", "вебразработка", "разработкасайтов",
    "мобильноеприложение", "разработкаприложений", "erp", "crm", "автоматизация",
    "цифровизация", "бизнеспроцессы", "аутсорсинг", "аутстаффинг", "cto",
    "itдиректор", "предприниматель", "основатель", "стартап", "mvp",
    "тендер", "управлениепроектами", "ии", "нейросети", "архитектура",
    "финтех", "девелопмент", "бизнес", "деловыесвязи", "сотрудничество",
]

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
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

CSV_FIELDS = ["title", "author", "date", "url", "views", "hashtag"]


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
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"    [!] ошибка запроса: {exc}", file=sys.stderr)
        return None


def _text(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _extract_int(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace(" ", " ").lower()
    m = re.search(r"([\d\s]+)\s*(k|к|m|м|тыс)?", cleaned)
    if not m:
        return ""
    digits = re.sub(r"\D", "", m.group(1))
    if not digits:
        return ""
    value = int(digits)
    suffix = m.group(2) or ""
    if suffix in ("k", "к", "тыс"):
        value *= 1000
    elif suffix in ("m", "м"):
        value *= 1_000_000
    return str(value)


def _find_post_containers(soup: BeautifulSoup) -> list[Tag]:
    containers = soup.find_all("article")
    if containers:
        return containers
    return soup.select(
        '[data-testid*="post"], [class*="post-card"], [class*="PostCard"], '
        '[class*="feed-item"], [class*="FeedItem"]'
    )


def _find_post_link(container: Tag) -> Tag | None:
    link = container.find("a", href=re.compile(r"/post/|/media/|/feed/"))
    if link:
        return link
    return container.find("a", href=True)


def _find_author(container: Tag) -> str:
    author_el = container.select_one(
        '[class*="author" i], [data-testid*="author" i], [class*="user-name" i]'
    )
    if author_el:
        return _text(author_el)
    profile_link = container.find("a", href=re.compile(r"^/[^/]+/?$"))
    return _text(profile_link)


def _find_date(container: Tag) -> str:
    time_el = container.find("time")
    if time_el:
        return time_el.get("datetime") or _text(time_el)
    date_el = container.select_one('[class*="date" i], [class*="time" i]')
    return _text(date_el)


def _find_views(container: Tag) -> str:
    candidates = container.select(
        '[class*="view" i], [aria-label*="просмотр" i], [title*="просмотр" i]'
    )
    for el in candidates:
        value = _extract_int(_text(el))
        if value:
            return value
    for el in container.find_all(string=re.compile(r"просмотр", re.I)):
        parent = el.parent
        if parent:
            value = _extract_int(_text(parent))
            if value:
                return value
    return ""


def parse_posts(html: str, tag: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []
    for container in _find_post_containers(soup):
        link = _find_post_link(container)
        if not link:
            continue
        url = urljoin(BASE_URL, link.get("href", ""))
        title_el = container.find(["h1", "h2", "h3"])
        title = _text(title_el) or _text(link)
        posts.append(Post(
            title=title,
            author=_find_author(container),
            date=_find_date(container),
            url=url,
            views=_find_views(container),
            hashtag=tag,
        ))
    return posts


def collect(tags: Iterable[str]) -> list[Post]:
    tags = list(tags)
    seen: dict[str, Post] = {}
    session = requests.Session()

    for i, tag in enumerate(tags, 1):
        url = HASHTAG_URL.format(tag=tag)
        print(f"[{i}/{len(tags)}] #{tag} → {url}")
        html = fetch(session, url)
        if html:
            found = parse_posts(html, tag)
            new = sum(1 for p in found if p.url and p.url not in seen)
            for p in found:
                if p.url and p.url not in seen:
                    seen[p.url] = p
            print(f"    постов на странице: {len(found)}, новых: {new}")
        if i < len(tags):
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    return list(seen.values())


def save_csv(posts: list[Post], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for p in posts:
            writer.writerow(asdict(p))


def main() -> int:
    posts = collect(HASHTAGS)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"posts_{ts}.csv"
    save_csv(posts, out)
    print(f"\nГотово. Уникальных постов: {len(posts)}")
    print(f"Файл: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
