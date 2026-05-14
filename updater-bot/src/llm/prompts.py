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

Reply with the commit-message line only. No quotes, no explanation.
"""

# News classifier: cheap yes/no on each scraped link.
NEWS_CLASSIFY_TEMPLATE = """\
Decide whether this scraped item is a real, news-worthy item suitable for the
HUJI AI Hub website's news feed.

News-worthy means: a substantive announcement, story, or update relevant to AI
research, AI education, AI industry partnerships, faculty achievements, new
courses or programs, grants, awards, or tech-transfer deals out of HUJI.

NOT news-worthy: navigation links, generic page titles ("About", "Contact"),
calls-to-action ("Read more", "Subscribe"), social media boilerplate,
generic university announcements unrelated to AI / CS / research.

SCRAPED ITEM:
- Source: {source_id}
- Title / link text: {title}
- URL: {url}
- Surrounding text snippet: {content_snippet}

Reply with strict JSON, nothing else:
{{
  "is_newsworthy": true | false,
  "confidence": 0.0-1.0,
  "reason": "<one short sentence>"
}}
"""

# News drafter: produces the full bilingual card.
# IMPORTANT formatting rules baked into the prompt:
# - No em dashes anywhere in rendered text (use commas, colons, parentheses)
# - Both Hebrew and English required for every field
# - Slug must be kebab-case, date-prefixed
NEWS_DRAFT_TEMPLATE = """\
Draft a complete bilingual news card for the HUJI AI Hub website based on the
scraped item below.

SCRAPED ITEM:
- Source: {source_id} ({source_name})
- Title / link text: {title}
- URL: {url}
- Snippet: {content_snippet}

Today's date: {today}

REQUIREMENTS (read carefully):
1. Output BOTH English and Hebrew for every field. Translate honestly. If the
   source is Hebrew, write the English; if the source is English, write the Hebrew.
2. NEVER use em dashes (—). Use commas, colons, parentheses, or restart the
   sentence. Em dashes are an absolute no.
3. Slug: kebab-case, date-prefixed. Format: {today}-<short-keywords>. Example:
   {today}-yissum-ai-startup-deal. Lowercase ASCII, hyphens only.
4. Title: under 80 chars. Headline-style, no clickbait.
5. Summary: 1 to 2 lines (under 200 chars). What happened + why it matters.
6. Body: 2 to 4 short paragraphs, plain markdown. Be factual, no marketing
   hype. Don't invent facts beyond what the snippet supports. If detail is
   missing, keep the body short and add a "needsReview" flag mentally (the
   editor will flesh it out).
7. SEO: seoTitle ends with " | HUJI AI Hub" (English) or " | מרכז AI האוניברסיטה העברית" (Hebrew).
   seoDescription is 130-180 chars, includes keywords naturally.
8. Keywords: 3-5 short search phrases the audience would actually type.
9. Tags: 1-3 lowercase kebab-case tags from this list when fits: faculty,
   research, industry, academics, grant, award, new-course, partnership,
   tech-transfer, student-life. Add others if needed.
10. Image: pick one from this list, or null if none fits. Pick by topical
    relevance (deep-learning visuals for ML stories, classroom shots for
    education stories, generic if nothing matches better):
{available_images}

Reply with strict JSON only, this exact shape, no preamble:
{{
  "slug": "string",
  "title": "string",
  "titleHe": "string",
  "summary": "string",
  "summaryHe": "string",
  "body": "string (markdown, multiple paragraphs OK)",
  "bodyHe": "string (markdown, multiple paragraphs OK)",
  "seoTitle": "string",
  "seoTitleHe": "string",
  "seoDescription": "string",
  "seoDescriptionHe": "string",
  "keywords": ["string", ...],
  "keywordsHe": ["string", ...],
  "tags": ["string", ...],
  "image": "string or null"
}}
"""
