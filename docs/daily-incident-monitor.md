# Daily Incident Monitor Automation

This repository publishes a static `daily-incident-monitor.html` page through GitHub Actions.
The workflow scans public RSS feeds once per day, asks the OpenAI API to classify and summarize
only relevant TPRM and supply chain incidents, then commits the generated static HTML update.

## Required GitHub Secret

Add this repository secret:

```text
OPENAI_API_KEY
```

Without the secret, the workflow will not publish unreviewed candidate items.

## Workflow

File:

```text
.github/workflows/daily-incident-monitor.yml
```

Default cadence:

```text
Daily at 06:15 UTC
```

This is 08:15 in Prague during summer time and 07:15 during winter time.

## Publishing Rules

The automation is intentionally conservative:

- publishes at most 8 incidents per day,
- reviews at most 35 candidate feed items per run,
- skips ordinary vulnerability news unless there is active exploitation, vendor impact, or a clear hot-fix action,
- requires one primary source or two independent reliable secondary sources,
- avoids duplicates already published in `automation/daily_incident_monitor.json`,
- does not publish if fewer than two feeds are reachable.

## Tunable Limits

These are set in the workflow and can be adjusted there:

```text
OPENAI_MODEL=gpt-5-mini
DAILY_MONITOR_MAX_CANDIDATES=35
DAILY_MONITOR_MAX_ITEMS_PER_FEED=12
DAILY_MONITOR_MAX_PUBLISHED=8
DAILY_MONITOR_MAX_OUTPUT_TOKENS=8000
DAILY_MONITOR_DAYS_BACK=3
```

## Manual Test

Run a feed-only dry run:

```bash
python scripts/daily_incident_monitor.py --dry-run --skip-openai
```

Run the full classifier without writing files:

```bash
OPENAI_API_KEY=... python scripts/daily_incident_monitor.py --dry-run
```
