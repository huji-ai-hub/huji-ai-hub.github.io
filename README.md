# HUJI AI Hub

The website for the AI Hub at the Hebrew University of Jerusalem: research, academic programs, faculty profiles, and industry collaboration. A bilingual (English / Hebrew) static site, built with Astro and deployed on Cloudflare Pages.

- **Live site:** https://huji-ai-hub.pages.dev
- **Repository:** https://github.com/huji-ai-hub/huji-ai-hub.github.io

The site replaces an older Drupal-based version. The design goal was that anyone (not just a developer) should be able to update content, and the next maintainer should inherit a project that doesn't depend on tribal knowledge to keep running.

---

## Quick reference: what to do if you want to…

| Goal | Where to go |
|---|---|
| Edit a faculty bio | `src/content/faculty/<slug>.md`. Open it on github.com, click the pencil, edit, commit |
| Add a new faculty member | Create a new `src/content/faculty/<their-name>.md` (copy an existing one as a template) and add their photo to `public/photos/` |
| Change homepage text | `src/content/pageContent/home.md` |
| Add or edit a research field | `src/content/fields/<slug>.md` |
| Update industry-page text | `src/content/pageContent/industry.md` (and `src/content/companies/<name>.md` for partners) |
| Update the page header / footer / language toggle | `src/layouts/Base.astro` |
| Add a new top-level page | New `.astro` file under `src/pages/` (and a parallel one under `src/pages/he/`) |
| See what the site builds to | `npm run build` (output in `dist/`) |
| Run locally | `npm install` then `npm run dev` (opens on `http://localhost:4321`) |

---

## How a content edit becomes a live page

```
edit a file → commit → open pull request → review → merge to main → automatic build → live in ~90 seconds
```

There are two ways to do the "edit a file" step, depending on who you are:

1. **In the browser.** Open the file on github.com, click the pencil icon, edit in the GitHub UI, save. GitHub creates the commit and prompts you to open a pull request. No software to install.
2. **On your computer.** Clone the repo, edit any file in your text editor of choice, commit, push. Suitable for someone who edits frequently or wants to preview locally first.

In both cases, no CMS login, no admin panel, no database. The repository is the content source of truth.

---

## Project structure

```
site/
├── src/
│   ├── content/                ← ALL editable content, one markdown file per item
│   │   ├── faculty/            ← One markdown file per faculty member
│   │   ├── fields/             ← Research fields (the grid + per-field pages)
│   │   ├── programs/           ← Academic programs (rendered as tabs on /academics)
│   │   ├── companies/          ← Industry partners + faculty-founded companies
│   │   ├── featured/           ← Featured blocks on landing pages
│   │   ├── featuredTalks/      ← Video talk blocks
│   │   ├── labs/               ← Lab spotlight cards
│   │   ├── pageContent/        ← Editable hero/landing text per page (home, research, industry…)
│   │   └── news/               ← News cards
│   ├── pages/                  ← Routes, each .astro file becomes a URL
│   │   ├── faculty/
│   │   ├── research/
│   │   └── he/                 ← Hebrew mirror of every English route
│   ├── layouts/
│   │   └── Base.astro          ← Page shell (head metadata, header, footer)
│   ├── components/             ← Reusable UI pieces
│   └── content.config.ts       ← Schema for content collections
├── public/
│   ├── images/                 ← Hero and section images
│   ├── photos/                 ← Faculty headshots
│   ├── favicon.svg
│   └── robots.txt
├── .github/workflows/
│   └── deploy.yml              ← Builds and publishes to GitHub Pages on every push to main
├── astro.config.mjs            ← Build configuration (one-line site URL)
├── package.json                ← Dependencies (3 packages: Astro core + sitemap integration + marked)
└── README.md                   ← This file
```

**Content vs code.** Content lives under `src/content/` (markdown) and `public/` (images). Code lives under `src/pages/`, `src/layouts/`, and `src/components/`. They share a repository but they're cleanly separated by folder, with different change patterns. A content edit doesn't touch any code; a code change doesn't touch any content. The build runs in either case. (Every piece of editable text now lives in markdown under `src/content/`; there is no longer a `src/data/` folder of TypeScript files.)

This is the standard pattern for content sites with the modern static-site frameworks (Astro, Next.js, Hugo, Eleventy). The older approach of separating into two systems, code in one place and content in a CMS database, solved a problem (rebuilding code was once expensive) that doesn't exist anymore. A static-site build runs in seconds; the operational cost of a database (backups, migrations, version compatibility, hosting) is no longer justified for a site that doesn't need user accounts or runtime-generated pages.

---

## Stack

| Piece | Choice | Why |
|---|---|---|
| Static-site generator | [Astro](https://astro.build) | Best current tool for content sites with multiple contributors. Markdown-first. Native Hebrew/RTL support. Zero JavaScript shipped to the browser unless explicitly added. |
| Content storage | Markdown files in the repository (`src/content/`) | Anyone can edit with a text editor. AI agents can write to markdown trivially. No CMS API required. |
| Hosting | [Cloudflare Pages](https://pages.cloudflare.com) | Per-pull-request preview URLs out of the box, free, fast CDN. Output is plain static files, so the host is interchangeable if needed. |
| Repository host | github.com | Outside HUJI institutional control, won't disappear if internal infrastructure changes. Standard tooling, free unlimited collaborators, GitHub Actions native. |
| Permissions | GitHub branch protection | Edits go through pull requests; only repo collaborators can merge. No site-level login required. |

---

## Languages and RTL

Every English route at `/foo` has a parallel Hebrew route at `/he/foo`. The `Base.astro` layout sets `<html lang="he" dir="rtl">` for Hebrew pages and the corresponding `lang/dir` for English. Hebrew uses the Heebo font; English uses Inter. Each page's English ↔ Hebrew counterpart is linked in the head via `<link rel="alternate" hreflang="...">` so search engines route language-specific queries correctly.

Faculty content is one markdown file per person, shared between languages. Each file already carries the Hebrew name and title (`nameHe`, `titleHe`), sourced from the CS school's Hebrew faculty page, so faculty render correctly on the Hebrew side. Bios are still English-only; adding Hebrew bios is a content change (add a `bioHe` frontmatter field, conditionally render in the Hebrew template), structurally supported and awaiting a translation pass.

---

## SEO

Every page emits:

- A canonical URL
- `hreflang` link tags for the EN ↔ HE pair (plus `x-default`)
- Open Graph and Twitter Card metadata for shared links
- A JSON-LD `Organization` schema (the Hub, with parent organization = the Hebrew University)

Faculty profile pages additionally emit a JSON-LD `Person` schema with name, title, affiliation, and `sameAs` links to their personal website and Google Scholar.

The site exposes a `sitemap-index.xml` (generated at build time from the actual routes) and a `robots.txt` that allows all crawlers and points at the sitemap.

After the site is publicly deployed: submit the sitemap to Google Search Console (`search.google.com/search-console`) and Bing Webmaster Tools. PageSpeed Insights (`pagespeed.web.dev`) gives a Lighthouse SEO/performance/accessibility report on any URL.

---

## Permissions and governance

- The `main` branch is protected: direct pushes are blocked.
- Changes land via pull request and require at least one approving review from a repo collaborator.
- Repo collaborators control who can merge.
- There is no separate site-level login. Authorization to edit the site = authorization to merge to `main` = membership in the GitHub repo with merge rights.

If a logged-in editing surface for non-technical editors is later required, a headless CMS (such as Decap CMS or Sanity Studio) can be layered on top without changing the storage model. The decision is deferred until there's a real demand.

---

## Hosting and DNS

The site builds to plain static files, so it can run on any static host. Currently it ships to two destinations in parallel:

- **Cloudflare Pages** at `https://huji-ai-hub.pages.dev`. Free tier, fast CDN, automatic per-pull-request preview URLs. Primary review surface.
- **GitHub Pages** at `https://huji-ai-hub.github.io`. Auto-deployed on every push to `main` by `.github/workflows/deploy.yml`. Live in parallel to Cloudflare; kept active as a fallback and as the candidate target for the HUJI subdomain CNAME.

**HUJI subdomain (target):** `ai-hub.cs.huji.ac.il`. The CS school's policy is that anything CS-related must be served from inside HUJI infrastructure (DNS audit confirmed: every `*.cs.huji.ac.il` subdomain points to a HUJI-internal IP). The agreed plan: a git hook syncs `main` from github.com to `github.cs.huji.ac.il`, and a HUJI CS server pulls the mirror and serves it at the target URL. Awaiting provisioning from CS IT. When the cutover happens, the only code change needed is updating the `site` field in `astro.config.mjs`.

Either the GitHub Pages or the Cloudflare deploy can stay running indefinitely as a preview / backup environment without affecting the production URL.

---

## Local development

Requires Node.js 22 or newer.

```bash
npm install     # install dependencies (one-time)
npm run dev     # start dev server at http://localhost:4321 (live reload on save)
npm run build   # build static output to dist/
npm run preview # preview the built output locally
```

That's the entire development surface.

---

## Departure-proofing

The project is designed so that whoever inherits it gets:

- A public GitHub repository with no missing credentials and no shadow infrastructure.
- This README, plus design rationale documents in the project workspace at `output/`.
- A standard, widely-used stack (Astro and Cloudflare Pages are both mainstream).
- A working deploy pipeline that requires no manual intervention.

There is no proprietary GUI, no custom CMS, no contractor-specific tooling. Anyone fluent in markdown and git can take over the editing flow. Anyone with web development experience can take over the code.

---

## Contact

For content corrections or to be added as a contributor, email [webmaster@cs.huji.ac.il](mailto:webmaster@cs.huji.ac.il).
