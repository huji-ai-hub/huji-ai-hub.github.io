import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const faculty = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/faculty' }),
  schema: z.object({
    name: z.string(),
    title: z.string(),
    lab: z.string(),
    field: z.enum([
      'machine-perception',
      'language-cognition',
      'foundations-of-learning',
      'biomed',
      'multi-agent',
      'cyber-crypto',
      'data-science',
      'human-centered',
    ]).optional(),
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

export const collections = { faculty, labs };
