# Weekly Content Automation

This repository has a scheduled GitHub Actions workflow that prepares a weekly article draft for approval.

## Schedule

The workflow runs every Monday at `06:00 UTC`.

That is approximately:
- `08:00` in Prague during summer time
- `07:00` in Prague during winter time

You can also run it manually from:

`Actions -> Weekly content draft -> Run workflow`

## What It Creates

Each run creates a pull request with draft files under:

`_drafts/weekly-content/<date>-<topic>/`

The PR contains:
- `article.html` - ready-to-review HTML article in the blog style
- `article.md` - editable Markdown version
- `linkedin-post.md` - LinkedIn post in Gabriel's existing short-form style
- `approval.md` - PR summary and approval notes
- `metadata.json` - topic metadata

The workflow does not publish the article. Publication remains a separate approval step.

## Required GitHub Secret

Add this repository secret:

`OPENAI_API_KEY`

Path in GitHub web UI:

`Repository -> Settings -> Secrets and variables -> Actions -> New repository secret`

Optional repository variable:

`OPENAI_MODEL`

Default model:

`gpt-5`

## Current Queue

The queue is stored in:

`automation/content_queue.json`

By default, the first queued topic is selected in the week starting `2026-08-24`, the second queued topic in the following week, and so on. For a manual run, you can override the topic by setting the workflow environment variable `TOPIC_ID` before running the script locally.

Current planned drafts:

1. `From Checkbox to Culture: Building a Third-Party Risk Program That Actually Works`
2. `NIS2 and the Extended Supply Chain: When Your Small Supplier Becomes Your Biggest Risk`

## Approval Workflow

1. Review the generated PR every Monday.
2. Edit the draft directly if needed.
3. Approve the article concept and LinkedIn text.
4. Publish in a separate PR by moving the final HTML into the site root and adding article cards to `index.html` and `articles.html`.
