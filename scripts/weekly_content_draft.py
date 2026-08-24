#!/usr/bin/env python3
"""Generate the next weekly blog article draft and LinkedIn approval copy."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "automation" / "content_queue.json"
PREPARED_DRAFTS_PATH = ROOT / "automation" / "prepared_drafts.json"
DRAFT_ROOT = ROOT / "_drafts" / "weekly-content"
OUTPUT_ENV = ROOT / ".weekly-content-output"


ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} - Gabriel Hasik</title>
  <meta name="description" content="{description}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0e0e0e; --bg2: #141414; --bg3: #1a1a1a; --border: #242424;
      --muted: #3a3a3a; --text-dim: #666; --text-mid: #999; --text: #d8d0c4;
      --text-hi: #f0e8dc; --accent: #d4821a; --accent2: #e8a84c; --accent-dim: #3a2208;
      --serif: 'Playfair Display', Georgia, serif; --mono: 'DM Mono', 'Courier New', monospace;
      --sans: 'DM Sans', system-ui, sans-serif;
    }}
    body {{ background: var(--bg); color: var(--text); font-family: var(--sans); font-weight: 300; line-height: 1.7; }}
    nav {{ position: fixed; top: 0; left: 0; right: 0; z-index: 100; display: flex; align-items: center; justify-content: space-between; padding: 1.25rem 3rem; background: var(--bg); border-bottom: 1px solid var(--border); }}
    .nav-logo {{ font-family: var(--serif); font-size: 1.1rem; font-weight: 700; color: var(--text-hi); text-decoration: none; letter-spacing: 0.02em; }}
    .nav-logo span, footer a {{ color: var(--accent); }}
    .nav-links {{ display: flex; gap: 2.5rem; list-style: none; }}
    .nav-links a, .back-link, .back-link-bottom {{ font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-dim); text-decoration: none; }}
    .article-hero {{ padding: 9rem 3rem 4rem; border-bottom: 1px solid var(--border); max-width: 860px; }}
    .back-link {{ display: inline-flex; margin-bottom: 2.5rem; }}
    .back-link::before, .back-link-bottom::before {{ content: '<-'; margin-right: 0.5rem; }}
    .article-cat {{ font-family: var(--mono); font-size: 0.68rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent); border: 1px solid var(--accent-dim); padding: 3px 10px; border-radius: 2px; display: inline-block; margin-bottom: 1.5rem; }}
    .article-title {{ font-family: var(--serif); font-size: clamp(2rem, 5vw, 3.2rem); font-weight: 700; color: var(--text-hi); line-height: 1.15; letter-spacing: -0.02em; margin-bottom: 1.5rem; }}
    .article-meta {{ font-family: var(--mono); font-size: 0.68rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-dim); display: flex; gap: 1rem; flex-wrap: wrap; }}
    .article-body {{ max-width: 720px; padding: 4rem 3rem 5rem; }}
    .article-body p {{ font-size: 1.05rem; margin-bottom: 1.5rem; line-height: 1.85; }}
    .article-body h2 {{ font-family: var(--serif); font-size: clamp(1.4rem, 3vw, 1.9rem); color: var(--text-hi); line-height: 1.2; margin: 3rem 0 1rem; }}
    .article-body h3 {{ font-family: var(--serif); font-size: 1.2rem; color: var(--text-hi); margin: 2rem 0 0.75rem; }}
    .article-body ul, .article-body ol {{ margin: 1rem 0 1.5rem 1.5rem; }}
    .article-body li {{ margin-bottom: 0.5rem; font-size: 1rem; line-height: 1.75; }}
    .article-body strong {{ color: var(--text-hi); font-weight: 500; }}
    .article-body em, .article-body a {{ color: var(--accent2); }}
    .article-body table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0; font-size: 0.9rem; }}
    .article-body th {{ font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); text-align: left; padding: 0.6rem 0.75rem; border-bottom: 2px solid var(--accent-dim); background: var(--bg2); }}
    .article-body td {{ padding: 0.7rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
    .insight-box {{ background: linear-gradient(180deg, rgba(212,130,26,0.08), rgba(212,130,26,0.02)); border: 1px solid var(--accent-dim); padding: 1.25rem; border-radius: 4px; margin: 1.75rem 0 2rem; }}
    .article-divider {{ border: none; border-top: 1px solid var(--border); margin: 2.5rem 0; }}
    footer {{ padding: 2.5rem 3rem; display: flex; justify-content: space-between; font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.12em; color: var(--muted); text-transform: uppercase; border-top: 1px solid var(--border); gap: 1rem; flex-wrap: wrap; }}
    footer a {{ text-decoration: none; }}
    @media (max-width: 768px) {{ nav {{ padding: 1rem 1.5rem; }} .nav-links {{ gap: 1.25rem; }} .article-hero {{ padding: 7rem 1.5rem 3rem; }} .article-body {{ padding: 3rem 1.5rem 4rem; }} footer {{ flex-direction: column; text-align: center; }} }}
  </style>
</head>
<body>
  <nav>
    <a class="nav-logo" href="../../index.html">G.<span>Hasik</span></a>
    <ul class="nav-links">
      <li><a href="../../index.html#about">About</a></li>
      <li><a href="../../index.html#blog">Writing</a></li>
      <li><a href="../../index.html#projects">Projects</a></li>
      <li><a href="../../index.html#contact">Contact</a></li>
    </ul>
  </nav>
  <div class="article-hero">
    <a class="back-link" href="../../index.html#blog">Back to Writing</a>
    <div class="article-cat">{category}</div>
    <h1 class="article-title">{title}</h1>
    <div class="article-meta"><span>{month}</span><span>&middot;</span><span>{read_time}</span><span>&middot;</span><span>Gabriel Hasik</span></div>
  </div>
  <div class="article-body">
{body_html}
    <hr class="article-divider" />
    <a class="back-link-bottom" href="../../index.html#blog">Back to Writing</a>
  </div>
  <footer>
    <span>&copy; 2026 Gabriel Hasik</span>
    <span>Built with intention &middot; <a href="https://gabrielhasik.com">gabrielhasik.com</a></span>
    <span>Cyber &middot; Risk &middot; Supply Chain</span>
  </footer>
</body>
</html>
"""


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def load_next_topic() -> dict:
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))["queue"]
    topic_override = os.environ.get("TOPIC_ID")
    if topic_override:
        for topic in queue:
            if topic["id"] == topic_override:
                return topic
        raise RuntimeError(f"Unknown TOPIC_ID: {topic_override}")

    start_date_raw = os.environ.get("QUEUE_START_DATE", "2026-08-24")
    start_date = dt.date.fromisoformat(start_date_raw)
    today = dt.date.fromisoformat(os.environ.get("DRAFT_DATE") or dt.date.today().isoformat())
    week_index = max(0, (today - start_date).days // 7)
    if week_index < len(queue):
        return queue[week_index]

    used_ids = set()
    if DRAFT_ROOT.exists():
        for metadata_path in DRAFT_ROOT.glob("*/metadata.json"):
            try:
                used_ids.add(json.loads(metadata_path.read_text(encoding="utf-8"))["topic_id"])
            except (KeyError, json.JSONDecodeError):
                continue
    for topic in queue:
        if topic["id"] not in used_ids:
            return topic
    return queue[-1]


def call_openai(topic: dict, draft_date: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it as a GitHub Actions secret.")

    model = os.environ.get("OPENAI_MODEL", "gpt-5")
    blog_url = f"{os.environ.get('BLOG_BASE_URL', 'https://gabrielhasik.com')}/{topic['link_slug']}"
    prompt = f"""
Create a ready-for-approval professional blog article and LinkedIn post for Gabriel Hasik.

Topic: {topic['title']}
Category: {topic['category']}
Angle: {topic['angle']}
Regulatory anchor: {topic['regulatory_anchor']}
Target date: {draft_date}
Expected final URL: {blog_url}

Style requirements:
- Write in English.
- Match Gabriel's blog style: analytical, practical, board/risk focused, direct, not corporate fluff.
- Audience: CISOs, risk managers, procurement leaders, IT auditors, executives.
- Article length: 1,800-2,600 words.
- Include practical sections, tables where useful, and clear executive questions.
- Include only claims that are defensible without inventing fake statistics. If using statistics, use cautious wording and cite the source in the references.
- Use references to primary regulation where relevant, especially EUR-Lex for NIS2 or DORA.
- LinkedIn post format should resemble Gabriel's example: short hook, context paragraph, why he wrote it, then "Read the full blog here: {blog_url}".

Return strict JSON only.
"""
    schema = {
        "type": "json_schema",
        "name": "weekly_content_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "description", "read_time", "body_html", "article_markdown", "linkedin_post", "approval_summary"],
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "read_time": {"type": "string"},
                "body_html": {"type": "string"},
                "article_markdown": {"type": "string"},
                "linkedin_post": {"type": "string"},
                "approval_summary": {"type": "string"}
            }
        }
    }
    payload = {
        "model": model,
        "input": prompt,
        "tools": [{"type": "web_search", "search_context_size": "low"}],
        "text": {"format": schema, "verbosity": "medium"},
        "max_output_tokens": 12000
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8")) from exc

    text_parts = []
    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_parts.append(content.get("text", ""))
    if not text_parts:
        raise RuntimeError(f"OpenAI response did not include output_text: {response_json}")
    return json.loads("".join(text_parts))


def load_prepared_draft(topic: dict, draft_date: str, reason: Exception) -> dict:
    if not PREPARED_DRAFTS_PATH.exists():
        raise RuntimeError(f"OpenAI failed and no prepared fallback file exists: {reason}") from reason

    drafts = json.loads(PREPARED_DRAFTS_PATH.read_text(encoding="utf-8"))
    content = drafts.get(topic["id"])
    if not content:
        raise RuntimeError(f"OpenAI failed and no prepared fallback exists for {topic['id']}: {reason}") from reason

    blog_url = f"{os.environ.get('BLOG_BASE_URL', 'https://gabrielhasik.com')}/{topic['link_slug']}"
    content = dict(content)
    content["linkedin_post"] = content["linkedin_post"].format(blog_url=blog_url)
    content["approval_summary"] = (
        content["approval_summary"].format(draft_date=draft_date, blog_url=blog_url)
        + "\n\nFallback note: this draft was created from `automation/prepared_drafts.json` "
        "because the OpenAI API call failed. Review it normally before publishing."
    )
    return content


def generate_content(topic: dict, draft_date: str) -> dict:
    try:
        return call_openai(topic, draft_date)
    except Exception as exc:
        if os.environ.get("ALLOW_PREPARED_FALLBACK", "true").lower() not in {"1", "true", "yes"}:
            raise
        print(f"OpenAI generation failed, using prepared fallback draft: {exc}", file=sys.stderr)
        return load_prepared_draft(topic, draft_date, exc)


def write_draft(topic: dict, content: dict, draft_date: str) -> dict:
    slug = slugify(topic["title"])
    draft_dir = DRAFT_ROOT / f"{draft_date}-{slug}"
    draft_dir.mkdir(parents=True, exist_ok=True)

    article_html = ARTICLE_TEMPLATE.format(
        title=html.escape(content["title"]),
        description=html.escape(content["description"]),
        category=html.escape(topic["category"]),
        month=dt.date.fromisoformat(draft_date).strftime("%B %Y"),
        read_time=html.escape(content["read_time"]),
        body_html=content["body_html"].strip(),
    )

    article_path = draft_dir / "article.html"
    article_md_path = draft_dir / "article.md"
    linkedin_path = draft_dir / "linkedin-post.md"
    approval_path = draft_dir / "approval.md"
    metadata_path = draft_dir / "metadata.json"

    article_path.write_text(article_html, encoding="utf-8")
    article_md_path.write_text(content["article_markdown"].strip() + "\n", encoding="utf-8")
    linkedin_path.write_text(content["linkedin_post"].strip() + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps({
        "topic_id": topic["id"],
        "topic_title": topic["title"],
        "draft_date": draft_date,
        "target_publish_slug": topic["link_slug"],
        "category": topic["category"]
    }, indent=2) + "\n", encoding="utf-8")

    approval = f"""## Weekly article draft ready for approval

Topic: {content["title"]}

{content["approval_summary"]}

Generated files:
- `{article_path.relative_to(ROOT)}`
- `{article_md_path.relative_to(ROOT)}`
- `{linkedin_path.relative_to(ROOT)}`
- `{metadata_path.relative_to(ROOT)}`

Publishing note:
This PR only contains a draft under `_drafts/weekly-content/`. It does not publish the article to the live blog. After approval, copy the final HTML into `{topic["link_slug"]}` and add the article card to `index.html` and `articles.html`.
"""
    approval_path.write_text(approval, encoding="utf-8")
    return {
        "draft_dir": draft_dir,
        "article_path": article_path,
        "linkedin_path": linkedin_path,
        "approval_path": approval_path,
    }


def write_output_env(topic: dict, paths: dict, draft_date: str) -> None:
    lines = {
        "topic_id": topic["id"],
        "topic_title": topic["title"],
        "draft_date": draft_date,
        "draft_dir": str(paths["draft_dir"].relative_to(ROOT)),
        "article_path": str(paths["article_path"].relative_to(ROOT)),
        "linkedin_path": str(paths["linkedin_path"].relative_to(ROOT)),
        "approval_path": str(paths["approval_path"].relative_to(ROOT)),
    }
    OUTPUT_ENV.write_text("\n".join(f"{key}={shlex.quote(value)}" for key, value in lines.items()) + "\n", encoding="utf-8")


def main() -> int:
    draft_date = os.environ.get("DRAFT_DATE") or dt.date.today().isoformat()
    topic = load_next_topic()
    content = generate_content(topic, draft_date)
    paths = write_draft(topic, content, draft_date)
    write_output_env(topic, paths, draft_date)
    print(f"Generated weekly content draft for: {topic['title']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"weekly_content_draft.py failed: {exc}", file=sys.stderr)
        raise
