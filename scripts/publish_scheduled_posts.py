#!/usr/bin/env python3
"""Publish prewritten weekly posts whose planned date is due."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
from email.utils import format_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_PATH = ROOT / "automation" / "scheduled_posts.json"
SCHEDULED_ARTICLES = ROOT / "_scheduled-posts" / "articles"
BASE_URL = "https://gabrielhasik.com"

INDEX_START = "<!-- SCHEDULED_POSTS_START -->"
INDEX_END = "<!-- SCHEDULED_POSTS_END -->"
RSS_START = "<!-- SCHEDULED_RSS_START -->"
RSS_END = "<!-- SCHEDULED_RSS_END -->"
SITEMAP_START = "<!-- SCHEDULED_SITEMAP_START -->"
SITEMAP_END = "<!-- SCHEDULED_SITEMAP_END -->"


def today() -> dt.date:
    override = __import__("os").environ.get("PUBLISH_DATE")
    return dt.date.fromisoformat(override) if override else dt.date.today()


def load_schedule() -> list[dict]:
    return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))["posts"]


def due_posts(posts: list[dict], publish_date: dt.date) -> list[dict]:
    due = [post for post in posts if dt.date.fromisoformat(post["publish_date"]) <= publish_date]
    return sorted(due, key=lambda post: post["publish_date"], reverse=True)


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    if not pattern.search(text):
        raise RuntimeError(f"Managed block markers not found: {start} / {end}")
    return pattern.sub(f"{start}\n{replacement}\n      {end}", text)


def blog_card(post: dict, indent: str = "      ") -> str:
    return f"""{indent}<a class="blog-card" href="{html.escape(post['slug'])}">
{indent}  <div class="blog-card-meta">
{indent}    <span class="cat">{html.escape(post['category'])}</span>
{indent}    <span>{html.escape(post['month'])}</span>
{indent}  </div>
{indent}  <h3>{html.escape(post['title'])}</h3>
{indent}  <p>{html.escape(post['description'])}</p>
{indent}  <div class="blog-card-footer">{html.escape(post['read_time'])} -</div>
{indent}</a>"""


def archive_card(post: dict, indent: str = "      ") -> str:
    return f"""{indent}<a class="archive-card" href="{html.escape(post['slug'])}">
{indent}  <div class="card-top">
{indent}    <div class="card-meta">
{indent}      <span class="card-cat">{html.escape(post['category'])}</span>
{indent}      <span class="card-date">{html.escape(post['month'])}</span>
{indent}    </div>
{indent}    <h2>{html.escape(post['title'])}</h2>
{indent}    <p>{html.escape(post['description'])}</p>
{indent}  </div>
{indent}  <div class="card-footer">
{indent}    <span>{html.escape(post['read_time'])}</span>
{indent}    <span class="card-arrow">&rarr;</span>
{indent}  </div>
{indent}</a>"""


def rss_item(post: dict) -> str:
    published = dt.datetime.combine(
        dt.date.fromisoformat(post["publish_date"]),
        dt.time(0, 0),
        tzinfo=dt.timezone(dt.timedelta(hours=2)),
    )
    url = f"{BASE_URL}/{post['slug']}"
    return f"""    <item>
      <title>{html.escape(post['title'])}</title>
      <link>{html.escape(url)}</link>
      <guid isPermaLink="true">{html.escape(url)}</guid>
      <pubDate>{format_datetime(published)}</pubDate>
      <description>{html.escape(post['description'])}</description>
    </item>"""


def sitemap_url(post: dict) -> str:
    url = f"{BASE_URL}/{post['slug']}"
    return f"""  <url>
    <loc>{html.escape(url)}</loc>
    <lastmod>{html.escape(post['publish_date'])}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>"""


def copy_due_articles(posts: list[dict]) -> None:
    for post in posts:
        source = SCHEDULED_ARTICLES / post["source"]
        target = ROOT / post["slug"]
        if not source.exists():
            raise RuntimeError(f"Scheduled source article missing: {source.relative_to(ROOT)}")
        if not target.exists():
            shutil.copyfile(source, target)


def update_index(posts: list[dict]) -> None:
    path = ROOT / "index.html"
    content = path.read_text(encoding="utf-8")
    cards = "\n\n".join(blog_card(post) for post in posts)
    path.write_text(replace_between(content, INDEX_START, INDEX_END, cards), encoding="utf-8")


def update_articles(posts: list[dict]) -> None:
    path = ROOT / "articles.html"
    content = path.read_text(encoding="utf-8")
    cards = "\n\n".join(archive_card(post) for post in posts)
    path.write_text(replace_between(content, INDEX_START, INDEX_END, cards), encoding="utf-8")


def update_feed(posts: list[dict], publish_date: dt.date) -> None:
    path = ROOT / "feed.xml"
    content = path.read_text(encoding="utf-8")
    items = "\n\n".join(rss_item(post) for post in posts)
    updated = replace_between(content, RSS_START, RSS_END, items)
    build_date = dt.datetime.combine(
        publish_date,
        dt.time(0, 0),
        tzinfo=dt.timezone(dt.timedelta(hours=2)),
    )
    updated = re.sub(
        r"<lastBuildDate>.*?</lastBuildDate>",
        f"<lastBuildDate>{format_datetime(build_date)}</lastBuildDate>",
        updated,
    )
    path.write_text(updated, encoding="utf-8")


def update_sitemap(posts: list[dict]) -> None:
    path = ROOT / "sitemap.xml"
    content = path.read_text(encoding="utf-8")
    urls = "\n".join(sitemap_url(post) for post in posts)
    path.write_text(replace_between(content, SITEMAP_START, SITEMAP_END, urls), encoding="utf-8")


def main() -> int:
    publish_date = today()
    posts = due_posts(load_schedule(), publish_date)
    if not posts:
        print(f"No scheduled posts due on {publish_date}.")
        return 0

    copy_due_articles(posts)
    update_index(posts)
    update_articles(posts)
    update_feed(posts, publish_date)
    update_sitemap(posts)
    print(f"Published scheduled posts due on {publish_date}: {len(posts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
