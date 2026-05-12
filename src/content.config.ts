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

const labs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/labs' }),
  schema: z.object({
    name: z.string(),
    lead: z.string(),
    website: z.string().url().optional(),
    order: z.number().optional(),
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

    // Long-form body, Hebrew lives in frontmatter (YAML literal block) so the
    // markdown body field can stay clean for the English text. Editors who only
    // know one language can edit just one side without confusing themselves.
    bodyHe: z.string(),                     // multi-paragraph Hebrew body (separate paragraphs with blank lines)

    // Editorial flags
    needsReview: z.boolean().default(false),       // true = content is a stub or scraped, flag in PR
    needsReviewNote: z.string().optional(),        // what specifically needs verification
  }),
});

export const collections = { faculty, labs, programs };
