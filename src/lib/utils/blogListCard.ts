import type { CollectionEntry } from "astro:content";
import type { MicroCMSContent } from "@/lib/microcms/types";
import { plainify } from "@/lib/utils/textConverter";

/** `Posts.astro` 用の一覧カード（Markdown / microCMS 共通） */
export type BlogListCard = {
  id: string;
  title: string;
  excerpt: string;
  /** サイト相対パス（`/images/...`）または絶対 URL */
  image?: string;
  date: Date;
  authors: string[];
  categories: string[];
};

export function collectionEntryToBlogListCard(
  post: CollectionEntry<"posts">,
): BlogListCard {
  return {
    id: post.id,
    title: post.data.title,
    excerpt: plainify(post.body ?? ""),
    image: post.data.image,
    date: post.data.date ?? new Date(),
    authors: post.data.authors,
    categories: post.data.categories,
  };
}

/** microCMS の API スキーマ例（管理画面のフィールド名に合わせて調整） */
export type MicroCMSBlogPostFields = {
  title: string;
  meta_title?: string;
  description?: string;
  /** リッチテキスト（HTML）。フィールド ID が `content` の場合に利用 */
  content?: string;
  /** 文字列 HTML、または microCMS のオブジェクト形式 */
  body?: string | { html?: string };
  image?: { url: string; height?: number; width?: number } | string;
  authors?: string[];
  categories?: string[] | { id?: string; name: string }[];
  tags?: string[] | { id?: string; name: string }[];
  products?: {
    fieldId: "product_card";
    title: string;
    image?: { url: string };
    amazon_url?: string;
    rakuten_url?: string;
    yahoo_url?: string;
    price?: string;
  }[];
};

function pickImageUrl(
  image: MicroCMSBlogPostFields["image"],
): string | undefined {
  if (!image) return undefined;
  return typeof image === "string" ? image : image.url;
}

export function pickCategories(
  categories: MicroCMSBlogPostFields["categories"],
): string[] {
  if (!categories?.length) return [];
  return categories.map((c) => (typeof c === "string" ? c : c.name));
}

export function pickTags(tags: MicroCMSBlogPostFields["tags"]): string[] {
  if (!tags?.length) return [];
  return tags.map((t) => (typeof t === "string" ? t : t.name));
}

/** 詳細ページ用：本文 HTML（`content` → `body` の順で解決） */
export function microCMSBodyHtml(
  post: MicroCMSContent<MicroCMSBlogPostFields>,
): string {
  if (post.content && typeof post.content === "string") return post.content;
  const b = post.body;
  if (typeof b === "string") return b;
  if (b && typeof b === "object" && typeof b.html === "string") return b.html;
  return "";
}

export function resolvePostImageSrc(
  image: string | undefined,
): string | undefined {
  if (!image) return undefined;
  if (image.startsWith("http://") || image.startsWith("https://"))
    return image;
  return import.meta.env.BASE_URL + image.replace(/^\//, "");
}

export function microCMSContentToBlogListCard(
  post: MicroCMSContent<MicroCMSBlogPostFields>,
): BlogListCard {
  const raw =
    post.description ??
    (typeof post.body === "string" ? post.body : "") ??
    (typeof post.content === "string" ? post.content : "");
  return {
    id: post.id,
    title: post.title,
    excerpt: plainify(raw),
    image: pickImageUrl(post.image),
    date: new Date(post.publishedAt),
    authors: post.authors ?? [],
    categories: pickCategories(post.categories),
  };
}

export function sortBlogListCardsByDate(cards: BlogListCard[]): BlogListCard[] {
  return [...cards].sort(
    (a, b) => new Date(b.date).valueOf() - new Date(a.date).valueOf(),
  );
}
