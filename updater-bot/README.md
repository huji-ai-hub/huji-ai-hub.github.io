# HUJI AI Hub: Updater Bot

A small Python program that runs once a week on GitHub Actions, scans the HUJI AI Hub website and a handful of HUJI sources for content that's gone out of date, and opens a single pull request proposing every change it found. A human reviews the PR and merges, edits, or closes it. No CMS, no logins, no surprises.

---

## 1. What this bot does

Every Monday at 03:00 UTC, the bot:

1. Loads the website's faculty list and content files.
2. Pulls candidate news from three live sources (configurable in `config.toml`):
   - The HUJI main news sitemap (`new.huji.ac.il/sitemap.xml`) plus Open Graph metadata per article.
   - A curated email inbox (`huji.ai.hub.bot.inbox@gmail.com`), where a human forwards HUJI newsletters and Scholar alerts. The bot reads via IMAP and splits multi-story newsletters into individual cards.
   - Each faculty member's personal site (one HTTP request each, throttled).
   Two more sources are wired up but currently disabled because they sit behind anti-bot walls: Yissum RSS (Cloudflare blocks runner IPs) and the HUJI CS school pages (F5 BIG-IP challenge). Re-enable in `config.toml` if you find a path through.
3. Checks the live site for dead links, missing/extra faculty entries, and stale dates.
4. Sends each candidate to Claude (Anthropic) twice: cheap Haiku for "is this AI-relevant" classification, better Sonnet for drafting the bilingual EN+HE card on items that pass.
5. Opens **one pull request** with every accepted change as a separate commit, plus a markdown summary you can skim in 2 minutes.

You review. You merge. The site redeploys.

If nothing changed, the bot opens no PR and logs `no changes proposed`.

---

## 2. One-time setup (do this once, ever)

Should take 20-30 minutes total.

### 2a. Create the bot's GitHub account

1. Open a private/incognito window so you don't sign out of your own GitHub.
2. Go to **github.com** → **Sign up**.
3. Username: `huji-ai-hub-bot`. Use any email you control (a Gmail alias like `ellastahls+hujibot@gmail.com` is fine).
4. Verify the email.

> _(Screenshot helpful here: GitHub signup page with the username filled in.)_

### 2b. Invite the bot to the website repo

While signed into your **personal** account:

1. Go to `github.com/huji-ai-hub/huji-ai-hub.github.io`.
2. **Settings** (gear icon, top of repo) → **Collaborators** (left sidebar) → **Add people**.
3. Type `huji-ai-hub-bot`, choose role: **Write**.
4. Sign into the bot account, accept the invite from your email.

> _(Screenshot helpful: Settings → Collaborators showing the invite.)_

### 2c. Generate a Personal Access Token (PAT) on the bot account

While signed in as `huji-ai-hub-bot`:

1. Profile picture (top right) → **Settings**.
2. Left sidebar → **Developer settings** (very bottom).
3. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
4. Fill in:
   - **Token name:** `huji-ai-hub-updater-bot`
   - **Expiration:** 1 year (you'll get an email reminder before it expires)
   - **Repository access:** *Only select repositories* → pick `huji-ai-hub.github.io`
   - **Repository permissions:**
     - **Contents:** Read and write
     - **Pull requests:** Read and write
     - (Leave everything else as "No access".)
5. Click **Generate token**. **Copy the token immediately**, you won't see it again.

> _(Screenshot helpful: the permissions selection screen.)_

### 2d. Get an Anthropic API key

1. Sign in (or create an account) at **console.anthropic.com**.
2. Left sidebar → **API Keys** → **Create Key**.
3. Name: `huji-ai-hub-updater`. Workspace: default.
4. Copy the key (starts with `sk-ant-`).

> The bot uses ~$0.50/run. The free starter credit covers many months.

### 2e. Add both as GitHub repo secrets

Back on your **personal** account, in the website repo:

1. **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Add four secrets:
   - Name: `ANTHROPIC_API_KEY`, Value: the Anthropic key from step 2d.
   - Name: `BOT_GITHUB_TOKEN`, Value: the PAT from step 2c.
   - Name: `BOT_INBOX_EMAIL`, Value: the bot Gmail address (e.g. `huji.ai.hub.bot.inbox@gmail.com`).
   - Name: `BOT_INBOX_APP_PASSWORD`, Value: a Google App Password for that Gmail (generate at `myaccount.google.com/apppasswords`; requires 2FA on the bot Gmail).

The last two are only needed if you keep the `email_inbox` source enabled. Without them the bot logs a warning and skips that source, which is fine for a faculty-pages-only deployment.

> _(Screenshot helpful: the Actions secrets page with all four entries.)_

### 2f. Push the bot to the repo

From your local checkout of the website repo:

```bash
git add updater-bot/
git commit -m "Add updater bot scaffold"
git push
```

### 2g. Move the workflow to its real home

The scaffold puts the workflow file in `updater-bot/.github/workflows/updater.yml` so it doesn't accidentally run before you're ready. Move it to where GitHub Actions looks for workflows:

```bash
mkdir -p .github/workflows
mv updater-bot/.github/workflows/updater.yml .github/workflows/
git add .github/workflows/updater.yml
git rm updater-bot/.github/workflows/updater.yml
git commit -m "Activate updater bot workflow"
git push
```

### 2h. Trigger the first run manually

1. Go to the repo → **Actions** tab.
2. Left sidebar → **Updater bot**.
3. **Run workflow** button (top right) → branch: `main` → **Run workflow**.
4. Wait ~5 minutes. Click into the run to watch the logs.

When it finishes, either:
- A pull request appears in the **Pull requests** tab → review it (see Section 5).
- The logs say `no changes proposed` → the bot saw nothing to update this week.

After this, the bot runs on its own every Monday at 03:00 UTC.

---

## 3. Running locally (optional, for debugging)

You don't need to run this locally for normal operation. Useful when a scraper breaks and you want to iterate quickly.

```bash
# install uv if you don't have it: https://github.com/astral-sh/uv
cd updater-bot
uv venv
source .venv/bin/activate     # macOS/Linux
.venv\Scripts\activate         # Windows PowerShell
uv pip install -e .

# copy the env template and fill in keys
cp .env.example .env
# edit .env, paste your ANTHROPIC_API_KEY and a GITHUB_TOKEN

# dry run: scrape + propose, but don't actually open a PR
python -m main --dry-run

# real run: opens a PR (use a test repo for this!)
python -m main
```

Logs go to stdout. Set `LOG_FORMAT=json` for structured logs.

---

## 4. Disabling a scraper, checker, or source

Edit `updater-bot/config.toml`. Find the relevant section, set `enabled = false`, commit. Examples:

```toml
[sources.email_inbox]
enabled = false   # stop reading the forwarded-email inbox this week

[sources.faculty_scholar]
enabled = false   # don't scrape Google Scholar this week

[checkers.dead_links]
enabled = false   # skip the dead-link check entirely
```

To pause the entire bot: set `enabled = false` under `[schedule]` and commit. (Or disable the workflow in the Actions tab.)

To change a URL (e.g., HUJI moved a page): edit the `url` field under that source's section. No code change needed.

To re-enable a source that's currently disabled because of an anti-bot wall (`huji_cs_faculty`, `huji_cs_news`, `huji_main_ai_news`, `yissum`): flip `enabled = true`, but first verify the source returns 200 from a GitHub Actions runner IP (they're aggressively blocked by Cloudflare and F5). A local 200 from your laptop doesn't predict a CI 200.

---

## 5. Reading a generated PR

Every bot PR has the same shape:

**Title:** `Auto-update YYYY-MM-DD: N changes (M high-confidence, K to review)`

**Body sections:**

1. **Summary table**: one row per proposed change, with file path, source, and confidence score. Use the checkboxes as a personal reading aid (checking them does nothing automatic).
2. **Per-change rationale**: for each change, the bot explains *why* and links to the source it scraped. This is the most important section. Read this before merging.
3. **Commits**: one per logical change, with a descriptive message and the source ID + confidence in the body.

**How to act:**

- **Looks good in full:** click **Merge pull request**. Site redeploys in ~2 minutes.
- **Want to keep some changes, drop others:** edit the files in the PR branch directly (GitHub web UI works), or revert specific commits before merging.
- **Want to edit the wording:** click any file in the PR's **Files changed** tab, click the pencil icon, edit, commit. Then merge.
- **Whole PR is wrong:** click **Close pull request** with a comment explaining why. The bot will not re-propose the same items next week (it remembers via `state/manifest.json`).

**Confidence scores** are not magic numbers; they're the bot's rough estimate. Use them as a sorting hint, not a decision rule:
- `> 0.9`: high confidence, usually safe to merge after a quick read.
- `0.7 to 0.9`: likely correct but worth checking the evidence link.
- `0.5 to 0.7`: verify before merging.
- Below 0.5: bot doesn't propose these.

---

## 6. Troubleshooting

| Symptom                                            | Likely cause / fix                                                                                                          |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Workflow run failed with `401 Unauthorized`        | `BOT_GITHUB_TOKEN` is wrong, expired, or missing the right permissions. Regenerate (step 2c) and update the secret (2e).     |
| Workflow run failed with `403` from Anthropic      | `ANTHROPIC_API_KEY` is wrong or you've hit a rate limit. Check console.anthropic.com.                                        |
| One scraper logs an error but the run continues    | Expected, scrapers are isolated. If the same one fails 3 weeks in a row, look at the scraper file (`src/scrapers/<name>.py`) and the test fixture (`tests/fixtures/`). HUJI probably changed their HTML. |
| Bot opens a PR with weird/wrong content           | Open an issue, reject the PR (close it with a comment). Look at `state/manifest.json` to see what triggered it.              |
| Bot hasn't opened a PR in weeks but logs success   | Probably nothing genuinely changed. Check the logs of the most recent run for `no changes proposed`.                         |
| You merged a PR and the site didn't update         | Check the Cloudflare Pages and the GitHub Pages deploy logs (both are separate workflows). The updater bot doesn't deploy; the existing site workflow does. |
| You want to test a scraper without opening a PR    | Run locally (Section 3) with `--dry-run`.                                                                                    |

---

## 7. Where to ask questions

If something breaks and you can't figure it out, the fastest path is:

1. Open the failing workflow run, copy the error log.
2. Go to **claude.ai** and paste the following prompt:

> I am the maintainer of a Python bot that runs on GitHub Actions and opens PRs against a static-site repo. The bot lives in `updater-bot/` of the repo `huji-ai-hub/huji-ai-hub.github.io`. Here is the design doc: [paste contents of `output/updater-bot-design.md`]. Here is the workflow log error I just got: [paste error]. What's the most likely cause and how do I fix it?

Claude will give you a concrete next step. If it's wrong, paste the result and iterate.

For larger changes (adding a new scraper, moving to a different LLM provider): open a Claude Code session in this repo and ask. The architecture is simple enough that most changes are 1 to 2 file edits.

---

## 8. Architecture summary

For full details see `output/updater-bot-design.md` in the website repo. Quick version:

```
GitHub Actions (cron) → main.py → scrapers/* → checkers/* → LLM filter → proposals → git commits → PR
                                       ↑
                              state/manifest.json (memory of what was seen)
```

Each stage is one folder. Each scraper, checker, and provider is one file. To add or replace anything, edit one file. Tests live in `tests/`.
