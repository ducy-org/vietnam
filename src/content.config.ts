import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const days = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/days' }),
  schema: z.object({
    date: z.string(),
    dayNumber: z.number().optional(),
    location: z.string().optional(),
    significant: z.boolean().default(false),
    month: z.string(),
    sources: z.array(z.string()).optional(),
    photoCount: z.number().optional(),
    documentCount: z.number().optional(),
  }),
});

export const collections = { days };
