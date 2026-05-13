"""All prompt templates for the bot. Keep them here so they're easy to audit."""

from __future__ import annotations

# System prompt is the same for every LLM call in a run — keep it stable so
# Anthropic prompt caching can hit. Render order is tools → system → messages,
# so any per-request data MUST go in the user message, not in here.
SYSTEM_PROMPT = """\
You are the content-update assistant for the HUJI AI Hub website.

The website is built from markdown files in a GitHub repository. A scheduled
bot scrapes HUJI sources and proposes changes to the site content. Your job
is to:

1. Decide whether a scraped item is genuinely worth proposing as a site change.
2. If yes, draft the markdown edit precisely.
3. Be conservative — when in doubt, do NOT propose. A human reviews every
   change before it goes live, but noisy proposals waste their attention.
4. Never invent facts. If the scraped data doesn't support a claim, leave the
   claim out. Only use what's in the evidence provided.
5. Match the existing voice of the site: short, factual, no marketing hype.

Output strictly in the JSON shape requested by each user message — no
preamble, no explanation outside the JSON.
"""

RELEVANCE_PROMPT_TEMPLATE = """\
Decide whether this scraped item is worth proposing as a change to the site.

EXISTING FILE CONTENT:
```markdown
{existing_content}
```

SCRAPED ITEM:
- Source: {source_id}
- Title: {title}
- URL: {url}
- Published: {published_at}
- Extra: {meta_json}

Reply with strict JSON:
{{
  "worth_proposing": true | false,
  "confidence": 0.0–1.0,
  "reason": "<one sentence>",
  "proposed_change_type": "frontmatter" | "body_append" | "body_replace" | "comment" | "none",
  "new_content_snippet": "<what to add/change, or empty string if none>"
}}
"""

STALE_DATE_CLASSIFY_TEMPLATE = """\
This is a date string in a HUJI AI Hub website page. Decide whether the date
describes a future event that has now passed (so the page is stale), or a past
event being correctly described in past tense (so it's fine).

Date found: {date}
Surrounding text: "{context}"

Reply with strict JSON:
{{
  "is_stale": true | false,
  "confidence": 0.0–1.0,
  "reason": "<one sentence>"
}}
"""

COMMIT_MESSAGE_TEMPLATE = """\
Write a one-line conventional-commit message for this change. Format:
<type>(<scope>): <summary>

Types: feat (new content), fix (broken/wrong), chore (formatting/metadata), docs.
Scope: short noun like "faculty", "links", "roster", "dates".
Summary: lowercase, imperative, under 60 chars total.

Change details:
- File: {file_path}
- Source: {source_id}
- Reason: {reason}

Reply with the commit-message line only — no quotes, no explanation.
"""
