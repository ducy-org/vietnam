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

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    date: z.string(),
    description: z.string(),
    image: z.string().optional(),
  }),
});

export const collections = { days, blog };
