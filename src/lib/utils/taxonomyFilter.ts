import { slugify } from "@/lib/utils/textConverter";

export const taxonomyFilter = (posts: any[], name: string, key: string) =>
  posts.filter((post) => {
    const list = post.data[name];
    if (!Array.isArray(list)) return false;

    return list.some((item: any) => {
      if (typeof item === "object" && item !== null) {
        // ID または 名前が一致すれば OK
        return item.id === key || slugify(item.name) === key || item.name === key;
      }
      // 文字列の場合は slugify した値または元の値が一致すれば OK
      const s = slugify(item);
      return s === key || item === key;
    });
  });

export default taxonomyFilter;
