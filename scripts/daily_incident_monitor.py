#!/usr/bin/env python3
"""Build the daily TPRM and supply chain incident monitor."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "automation" / "daily_incident_monitor.json"
PAGE_PATH = ROOT / "daily-incident-monitor.html"
BASE_URL = "https://gabrielhasik.com"
TIMEZONE = ZoneInfo("Europe/Prague")

INCIDENTS_START = "<!-- DAILY_INCIDENTS_START -->"
INCIDENTS_END = "<!-- DAILY_INCIDENTS_END -->"

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
MAX_CANDIDATES = int(os.environ.get("DAILY_MONITOR_MAX_CANDIDATES", "35"))
MAX_ITEMS_PER_FEED = int(os.environ.get("DAILY_MONITOR_MAX_ITEMS_PER_FEED", "12"))
MAX_PUBLISHED = int(os.environ.get("DAILY_MONITOR_MAX_PUBLISHED", "8"))
MAX_OUTPUT_TOKENS = int(os.environ.get("DAILY_MONITOR_MAX_OUTPUT_TOKENS", "8000"))
DAYS_BACK = int(os.environ.get("DAILY_MONITOR_DAYS_BACK", "3"))
PUBLISH_EMPTY_DAYS = os.environ.get("DAILY_MONITOR_PUBLISH_EMPTY_DAYS", "true").lower() == "true"

SOURCE_FEEDS = [
    {
        "name": "CISA Cybersecurity Advisories",
        "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
        "source_type": "primary",
    },
    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "source_type": "secondary",
    },
    {
        "name": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "source_type": "secondary",
    },
    {
        "name": "KrebsOnSecurity",
        "url": "https://krebsonsecurity.com/feed/",
        "source_type": "secondary",
    },
    {
        "name": "SecurityWeek",
        "url": "https://www.securityweek.com/feed/",
        "source_type": "secondary",
    },
    {
        "name": "The Register Security",
        "url": "https://www.theregister.com/security/headlines.atom",
        "source_type": "secondary",
    },
    {
        "name": "PortSwigger Daily Swig",
        "url": "https://portswigger.net/daily-swig/rss",
        "source_type": "secondary",
    },
    {
        "name": "FreightWaves",
        "url": "https://www.freightwaves.com/feed",
        "source_type": "secondary",
    },
]

RELEVANCE_TERMS = [
    "breach",
    "ransomware",
    "supply chain",
    "supplier",
    "vendor",
    "third-party",
    "third party",
    "outsourc",
    "saas",
    "cloud",
    "managed service",
    "msp",
    "software update",
    "dependency",
    "npm",
    "pypi",
    "github",
    "customer data",
    "data leak",
    "outage",
    "disruption",
    "port",
    "shipping",
    "logistics",
    "freight",
    "sanction",
    "cve",
    "zero-day",
    "critical vulnerability",
    "exploit",
]


@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    source: str
    source_type: str
    published: str
    summary: str

    def as_prompt_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "source_type": self.source_type,
            "published": self.published,
            "summary": self.summary[:900],
        }


def today() -> dt.date:
    override = os.environ.get("MONITOR_DATE")
    if override:
        return dt.date.fromisoformat(override)
    return dt.datetime.now(TIMEZONE).date()


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GabrielHasikDailyIncidentMonitor/1.0 (+https://gabrielhasik.com/monitoring.html)"
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def text_of(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return re.sub(r"\s+", " ", element.text).strip()


def child_text(item: ET.Element, names: tuple[str, ...]) -> str:
    for child in item:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in names and child.text:
            return re.sub(r"\s+", " ", child.text).strip()
    return ""


def item_link(item: ET.Element) -> str:
    for child in item:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text:
                return child.text.strip()
    return child_text(item, ("guid", "id"))


def parse_date(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(TIMEZONE)


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def parse_feed(feed: dict, cutoff: dt.datetime) -> tuple[list[Candidate], bool]:
    try:
        data = fetch_url(feed["url"])
        root = ET.fromstring(data)
    except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
        print(f"Feed skipped: {feed['name']} ({exc})", file=sys.stderr)
        return [], False

    items = [
        element
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}
    ]
    candidates: list[Candidate] = []
    for item in items[:MAX_ITEMS_PER_FEED]:
        title = child_text(item, ("title",))
        url = item_link(item)
        published_raw = child_text(item, ("published", "updated", "pubdate", "date"))
        published = parse_date(published_raw)
        if published and published < cutoff:
            continue

        summary = strip_html(child_text(item, ("summary", "description", "content", "encoded")))
        haystack = f"{title} {summary}".lower()
        if not title or not url or not any(term in haystack for term in RELEVANCE_TERMS):
            continue

        candidates.append(
            Candidate(
                title=title,
                url=url,
                source=feed["name"],
                source_type=feed["source_type"],
                published=published.isoformat() if published else "",
                summary=summary,
            )
        )
    return candidates, True


def candidate_key(candidate: Candidate) -> str:
    normalized = urllib.parse.urlparse(candidate.url)
    clean_url = normalized._replace(query="", fragment="").geturl().lower()
    return hashlib.sha256(clean_url.encode("utf-8")).hexdigest()


def collect_candidates(run_date: dt.date) -> tuple[list[Candidate], int]:
    cutoff = dt.datetime.combine(run_date - dt.timedelta(days=DAYS_BACK), dt.time.min, tzinfo=TIMEZONE)
    seen: set[str] = set()
    candidates: list[Candidate] = []
    successful_feeds = 0
    for feed in SOURCE_FEEDS:
        feed_candidates, success = parse_feed(feed, cutoff)
        if success:
            successful_feeds += 1
        for candidate in feed_candidates:
            key = candidate_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
            if len(candidates) >= MAX_CANDIDATES:
                return candidates, successful_feeds
        time.sleep(0.2)
    return candidates, successful_feeds


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"days": []}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def published_urls(state: dict) -> set[str]:
    urls: set[str] = set()
    for day in state.get("days", []):
        for incident in day.get("incidents", []):
            for source in incident.get("sources", []):
                urls.add(source.get("url", ""))
    return urls


def call_openai(candidates: list[Candidate], existing_urls: set[str], run_date: dt.date) -> list[dict]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not configured; no incidents generated.")
        return []

    prompt = f"""
You are preparing Gabriel Hasik's Daily TPRM & Supply Chain Incident Monitor for {run_date.isoformat()}.

Task:
Review the candidate feed items and return only confirmed incidents relevant to third-party risk management,
software supply chain risk, vendor incidents, business-critical outages, supplier data exposure, logistics disruption,
sanctions/export-control supply chain exposure, or critical supplier continuity.

Hard publishing rules:
- Publish at most {MAX_PUBLISHED} incidents.
- Do not publish ordinary vulnerability news unless there is active exploitation, a vendor/supplier impact, or a credible hot-fix action for TPRM/security teams.
- Do not publish opinion pieces, generic trend reports, product launches, or weakly related cybersecurity news.
- Each published incident must have either at least one primary source or at least two independent reliable secondary sources.
- If confidence is low, exclude the item.
- Use only the facts present in the candidates. Do not invent victims, affected data, timelines, or impact.
- Keep wording concise and operational.

Return JSON only with this shape:
{{
  "incidents": [
    {{
      "title": "short factual title",
      "category": "TPRM | Software supply chain | Vendor outage | Data breach | Logistics | Geopolitical supply chain | Regulatory",
      "severity": "High | Medium | Low",
      "confidence": "Primary source | Two-source corroborated",
      "what_happened": "1-2 sentences",
      "why_it_matters": "1-2 sentences for risk/procurement/security teams",
      "hot_fix": ["short action", "short action", "short action"],
      "sources": [{{"name": "source name", "url": "source url"}}]
    }}
  ]
}}

Already published URLs to avoid:
{json.dumps(sorted(existing_urls)[-200:], ensure_ascii=False)}

Candidates:
{json.dumps([candidate.as_prompt_dict() for candidate in candidates], ensure_ascii=False)}
"""
    payload = {
        "model": MODEL,
        "input": textwrap.dedent(prompt).strip(),
        "text": {"format": {"type": "json_object"}},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API request failed: {exc.code} {body}") from exc

    output_text = data.get("output_text", "")
    if not output_text:
        parts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    parts.append(content.get("text", ""))
        output_text = "\n".join(parts)

    output_text = output_text.strip()
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text, flags=re.IGNORECASE | re.DOTALL)
    parsed = json.loads(output_text)
    return parsed.get("incidents", [])


def source_is_allowed(incident: dict) -> bool:
    sources = incident.get("sources", [])
    source_urls = {source.get("url", "") for source in sources if source.get("url")}
    if not source_urls:
        return False
    primary_names = {
        feed["name"].lower()
        for feed in SOURCE_FEEDS
        if feed["source_type"] == "primary"
    }
    has_primary = any(source.get("name", "").lower() in primary_names for source in sources)
    return has_primary or len(source_urls) >= 2


def normalize_incidents(incidents: list[dict], existing_urls: set[str]) -> list[dict]:
    normalized: list[dict] = []
    seen_titles: set[str] = set()
    for incident in incidents:
        sources = [
            {"name": str(source.get("name", "")).strip(), "url": str(source.get("url", "")).strip()}
            for source in incident.get("sources", [])
            if source.get("name") and source.get("url")
        ]
        if not sources:
            continue
        if any(source["url"] in existing_urls for source in sources):
            continue
        if not source_is_allowed({**incident, "sources": sources}):
            continue

        title = str(incident.get("title", "")).strip()
        key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        if not title or key in seen_titles:
            continue
        seen_titles.add(key)

        hot_fix = [str(action).strip() for action in incident.get("hot_fix", []) if str(action).strip()]
        normalized.append(
            {
                "title": title[:160],
                "category": str(incident.get("category", "TPRM")).strip()[:60],
                "severity": str(incident.get("severity", "Medium")).strip().title(),
                "confidence": str(incident.get("confidence", "Primary source")).strip()[:80],
                "what_happened": str(incident.get("what_happened", "")).strip()[:700],
                "why_it_matters": str(incident.get("why_it_matters", "")).strip()[:700],
                "hot_fix": hot_fix[:4],
                "sources": sources[:4],
            }
        )
        if len(normalized) >= MAX_PUBLISHED:
            break
    return normalized


def day_exists(state: dict, run_date: dt.date) -> bool:
    return any(day.get("date") == run_date.isoformat() for day in state.get("days", []))


def add_day(state: dict, run_date: dt.date, incidents: list[dict]) -> bool:
    if day_exists(state, run_date):
        print(f"Daily incident monitor already has an entry for {run_date}.")
        return False
    if not incidents and not PUBLISH_EMPTY_DAYS:
        print("No qualifying incidents found; empty-day publishing disabled.")
        return False
    state.setdefault("days", []).insert(
        0,
        {
            "date": run_date.isoformat(),
            "generated_at": dt.datetime.now(TIMEZONE).isoformat(timespec="seconds"),
            "incidents": incidents,
        },
    )
    return True


def format_date(date_value: str) -> str:
    value = dt.date.fromisoformat(date_value)
    return value.strftime("%d %b %Y")


def render_source_links(sources: list[dict]) -> str:
    links = []
    for source in sources:
        links.append(
            f'<a href="{html.escape(source["url"], quote=True)}" rel="noopener" target="_blank">'
            f'{html.escape(source["name"])}</a>'
        )
    return " ".join(links)


def render_incident(incident: dict) -> str:
    hot_fix_items = "\n".join(f"            <li>{html.escape(action)}</li>" for action in incident.get("hot_fix", []))
    return f"""        <article class="incident-card severity-{html.escape(incident.get('severity', 'Medium').lower())}">
          <div class="incident-meta">
            <span>{html.escape(incident.get('severity', 'Medium'))}</span>
            <span>{html.escape(incident.get('category', 'TPRM'))}</span>
            <span>{html.escape(incident.get('confidence', 'Primary source'))}</span>
          </div>
          <h3>{html.escape(incident.get('title', 'Untitled incident'))}</h3>
          <div class="incident-body">
            <p><strong>What happened:</strong> {html.escape(incident.get('what_happened', ''))}</p>
            <p><strong>Why it matters:</strong> {html.escape(incident.get('why_it_matters', ''))}</p>
            <div>
              <strong>Hot fix:</strong>
              <ol>
{hot_fix_items}
              </ol>
            </div>
          </div>
          <div class="incident-sources">Sources: {render_source_links(incident.get('sources', []))}</div>
        </article>"""


def render_day(day: dict) -> str:
    incidents = day.get("incidents", [])
    if incidents:
        body = "\n\n".join(render_incident(incident) for incident in incidents)
    else:
        body = """        <article class="incident-card empty-day">
          <div class="incident-meta">
            <span>No qualifying incidents</span>
          </div>
          <h3>No publishable TPRM or supply chain incident met the source-confidence threshold.</h3>
          <p>The scan ran, but weakly sourced, duplicate, or low-relevance items were held back.</p>
        </article>"""
    return f"""      <section class="daily-block">
        <div class="day-heading">
          <span>{html.escape(format_date(day["date"]))}</span>
          <span>{len(incidents)} incident{'s' if len(incidents) != 1 else ''}</span>
        </div>
{body}
      </section>"""


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    if not pattern.search(text):
        raise RuntimeError(f"Managed block markers not found: {start} / {end}")
    return pattern.sub(f"{start}\n{replacement}\n      {end}", text)


def update_page(state: dict, run_date: dt.date) -> None:
    content = PAGE_PATH.read_text(encoding="utf-8")
    days_html = "\n\n".join(render_day(day) for day in state.get("days", [])[:90])
    updated = replace_between(content, INCIDENTS_START, INCIDENTS_END, days_html)
    updated = re.sub(
        r'<span id="last-updated">.*?</span>',
        f'<span id="last-updated">{html.escape(format_date(run_date.isoformat()))}</span>',
        updated,
    )
    PAGE_PATH.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch and classify without writing files.")
    parser.add_argument("--skip-openai", action="store_true", help="Only test feed collection and page rendering.")
    args = parser.parse_args()

    run_date = today()
    state = load_state()
    candidates, successful_feeds = collect_candidates(run_date)
    print(f"Collected {len(candidates)} candidate items from {successful_feeds} reachable feeds.")

    if successful_feeds < 2:
        print("Fewer than two feeds were reachable; not publishing a daily monitor entry.")
        return 0

    incidents: list[dict] = []
    if candidates and not args.skip_openai:
        if not os.environ.get("OPENAI_API_KEY"):
            print("OPENAI_API_KEY is not configured; not publishing unreviewed candidates.")
            return 0
        incidents = normalize_incidents(call_openai(candidates, published_urls(state), run_date), published_urls(state))
    print(f"Qualified incidents: {len(incidents)}")

    if args.dry_run:
        print(json.dumps({"date": run_date.isoformat(), "incidents": incidents}, indent=2, ensure_ascii=False))
        return 0

    if add_day(state, run_date, incidents):
        save_state(state)
        update_page(state, run_date)
        print(f"Updated daily incident monitor for {run_date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
