import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const faculty = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/faculty' }),
  schema: z.object({
    name: z.string(),
    title: z.string(),
    lab: z.string(),
    fields: z.array(z.enum([
      'machine-perception',
      'language-cognition',
      'foundations-of-learning',
      'biomed',
      'multi-agent',
      'cyber-crypto',
      'data-science',
      'human-centered',
    ])).optional(),
    photo: z.string().optional(),
    website: z.string().url().optional(),
    scholar: z.string().url().optional(),
    areas: z.array(z.string()).optional(),
    order: z.number().optional(),
  }),
});

// Lab spotlights, one markdown file per lab.
// Rendered as the "Spotlight: Our Labs" grid on /research and /he/research.
// Add a new lab = drop a new file in src/content/labs/ with the same shape.
const labs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/labs' }),
  schema: z.object({
    name: z.string(),                       // English display name, e.g. "Schwartz Lab"
    nameHe: z.string(),                     // Hebrew display name
    description: z.string(),                // one-line summary for the card (EN)
    descriptionHe: z.string(),              // one-line summary for the card (HE)
    image: z.string(),                      // path under /public, e.g. "/images/labs/schwartzman.png"
    url: z.string().url(),                  // external lab website
    order: z.number().default(99),          // grid order, lower numbers first
  }),
});

// Research fields. One markdown file per field under src/content/fields/.
// Rendered as the "Fields of Research" grid on /research, AND each field has
// its own detail page at /research/<slug>. The markdown body holds the
// long-form English description; bodyHe holds the long-form Hebrew.
const fields = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/fields' }),
  schema: z.object({
    slug: z.string(),                       // URL path, e.g. "machine-perception"
    title: z.string(),
    titleHe: z.string(),
    subtitle: z.string(),                   // one-line summary for the field detail page
    subtitleHe: z.string(),
    intro: z.string(),                      // 1-2 sentence intro shown on /research card
    introHe: z.string(),
    gradient: z.string().optional(),        // CSS gradient fallback when no image
    image: z.string().optional(),           // path under /public
    order: z.number().default(99),
    bodyHe: z.string().default(''),         // long-form Hebrew body for detail page (optional)
  }),
});

// Highlighted "featured" blocks on landing pages.
// One markdown file per block. The `page` field tells the system which page
// to render it on. Add a new featured block = drop a new file with the right
// page slug.
//
// Examples: "Beyond Human Vision: The Machine Perception Group" on /research,
// "Industrial Affiliates Program" on /industry.
const featured = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/featured' }),
  schema: z.object({
    page: z.enum(['research', 'industry', 'academics', 'about']),
    title: z.string(),
    titleHe: z.string(),
    body: z.string(),                       // 1-3 sentences (EN)
    bodyHe: z.string(),                     // 1-3 sentences (HE)
    image: z.string(),                      // path under /public
    ctaLabel: z.string(),                   // button text (EN), e.g. "Read more →"
    ctaLabelHe: z.string(),                 // button text (HE)
    ctaHref: z.string(),                    // where the button goes (external URL or internal /path)
    order: z.number().default(99),
  }),
});

// Per-landing-page editable text (hero title/body + optional secondary intro).
// One markdown file per landing page. Schema is intentionally permissive so
// that pages with extra sections (like /research's vision block) can use the
// optional intro fields without forcing other pages to declare them empty.
const pageContent = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/pageContent' }),
  schema: z.object({
    page: z.enum(['research', 'industry', 'academics', 'about', 'faculty', 'news']),
    heroTitle: z.string(),
    heroTitleHe: z.string(),
    heroBody: z.string(),
    heroBodyHe: z.string(),
    // Optional secondary intro/vision section
    introTitle: z.string().optional(),
    introTitleHe: z.string().optional(),
    introBody: z.string().optional(),
    introBodyHe: z.string().optional(),
  }),
});

// Academic programs, one markdown file per program.
// Each file is rendered as a tab on /academics and (mirrored) /he/academics.
// Frontmatter holds the structured fields; the markdown body holds the long description.
const programs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/programs' }),
  schema: z.object({
    // Identity
    slug: z.string(),                       // anchor id used in URL hash, e.g. "matar"
    name: z.string(),                       // English display name
    nameHe: z.string(),                     // Hebrew display name
    tagline: z.string(),                    // English one-line summary, used in the tab label area
    taglineHe: z.string(),                  // Hebrew one-line summary

    // Categorization
    degreeLevel: z.enum(['bsc', 'msc', 'phd', 'mixed']),
    type: z.enum(['emphasis', 'major', 'honors-track', 'minor', 'cross-faculty']),
    faculty: z.string().optional(),         // e.g. "School of CS & Engineering"
    facultyHe: z.string().optional(),

    // Links
    officialWebsite: z.string().url().optional(),
    courseListUrl: z.string().url().optional(),
    structurePdfUrl: z.string().url().optional(),
    registrationUrl: z.string().url().optional(),

    // Display
    image: z.string().optional(),           // hero image path (under /public)
    order: z.number().default(99),          // tab ordering, lower numbers first

    // SEO
    seoTitle: z.string().optional(),        // overrides the auto-generated <title> on the page
    seoTitleHe: z.string().optional(),
    seoDescription: z.string(),             // meta description (English)
    seoDescriptionHe: z.string(),           // meta description (Hebrew)
    keywords: z.array(z.string()).optional(),     // English keyword cues
    keywordsHe: z.array(z.string()).optional(),   // Hebrew keyword cues

    // Quick-facts strip rendered as chips at the top of the program panel.
    // Each entry: {label, value} with optional Hebrew counterparts.
    highlights: z.array(z.object({
      label: z.string(),
      value: z.string(),
      labelHe: z.string().optional(),
      valueHe: z.string().optional(),
    })).default([]),

    // Boxed callouts at the bottom of the panel. Short, scannable.
    whoItsFor: z.string().optional(),
    whoItsForHe: z.string().optional(),
    whatComesAfter: z.string().optional(),
    whatComesAfterHe: z.string().optional(),

    // Long-form body, Hebrew lives in frontmatter (YAML literal block) so the
    // markdown body field can stay clean for the English text. Editors who only
    // know one language can edit just one side without confusing themselves.
    bodyHe: z.string(),                     // multi-paragraph Hebrew body (separate paragraphs with blank lines)

    // Editorial flags
    needsReview: z.boolean().default(false),       // true = content is a stub or scraped, flag in PR
    needsReviewNote: z.string().optional(),        // what specifically needs verification
  }),
});

// News items. One markdown file per item under src/content/news/.
// Bot-generated items land here as PRs; humans review + merge.
// English body lives in the markdown body (under the frontmatter); Hebrew body
// lives in the `bodyHe` frontmatter field (YAML literal block).
const news = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/news' }),
  schema: z.object({
    // Identity
    slug: z.string(),                        // url path, e.g. "2026-05-13-yissum-ai-deal"
    title: z.string(),                       // English headline
    titleHe: z.string(),                     // Hebrew headline

    // Display
    summary: z.string(),                     // 1-2 lines for cards (EN)
    summaryHe: z.string(),                   // 1-2 lines for cards (HE)
    date: z.coerce.date(),                   // ISO date; controls archive sort order
    image: z.string().optional(),            // hero image path under /public
    featured: z.boolean().default(false),    // surfaced on the homepage
    tags: z.array(z.string()).default([]),

    // Optional override: when set, the homepage news card links here instead
    // of /news/<slug>. Use a path that starts with /, no language prefix
    // (the homepage adds /he for the Hebrew side). Example: "/academics/".
    linkTo: z.string().optional(),

    // Source attribution. Set when the item is bot-generated from an external page.
    sourceUrl: z.string().url().optional(),
    sourceName: z.string().optional(),       // human label, e.g. "Yissum", "HUJI News"

    // SEO
    seoTitle: z.string().optional(),
    seoTitleHe: z.string().optional(),
    seoDescription: z.string(),
    seoDescriptionHe: z.string(),
    keywords: z.array(z.string()).optional(),
    keywordsHe: z.array(z.string()).optional(),

    // Hebrew long-form body (markdown). English body sits in the file body.
    bodyHe: z.string(),

    // Editorial flags
    needsReview: z.boolean().default(false),
    needsReviewNote: z.string().optional(),
  }),
});

export const collections = { faculty, labs, fields, featured, pageContent, programs, news };
