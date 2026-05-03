import { defineCollection, z } from "astro:content";

const postsCollection = defineCollection({
  schema: z.object({
    title: z.string(),
    meta_title: z.string().optional(),
    description: z.string().optional(),
    date: z.date().optional(),
    image: z.string().optional(),
    authors: z.array(z.string()).default([]),
    categories: z.array(
      z.union([
        z.string(),
        z.object({
          id: z.string(),
          name: z.string(),
        }),
      ])
    ).default([]),
    tags: z.array(z.string()).default([]),
    products: z.array(
      z.object({
        title: z.string(),
        image: z.object({
          url: z.string().optional(),
        }).optional(),
        amazon_url: z.string().optional(),
        rakuten_url: z.string().optional(),
        yahoo_url: z.string().optional(),
        price: z.string().optional(),
      })
    ).optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = {
  posts: postsCollection,
};
