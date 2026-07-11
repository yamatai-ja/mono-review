import { toTaxonomyTerm } from "@/lib/utils/taxonomy";

export const taxonomyFilter = (posts: any[], name: string, key: string) =>
  posts.filter((post) => {
    const list = post.data[name];
    if (!Array.isArray(list)) return false;

    return list.some((item: any) => {
      const term = toTaxonomyTerm(item);
      return term.id === key || term.name === key;
    });
  });

export default taxonomyFilter;
