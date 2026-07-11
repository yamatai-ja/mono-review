import type { CollectionEntry } from "astro:content";

import { slugify } from "@/lib/utils/textConverter";

export type AuthorEntry = CollectionEntry<"authors">;

export const resolveAuthor = (
  reference: string,
  authors: AuthorEntry[],
): AuthorEntry | undefined => {
  const normalizedReference = slugify(reference);

  return authors.find(
    (author) =>
      slugify(author.id) === normalizedReference ||
      slugify(author.data.title) === normalizedReference,
  );
};
