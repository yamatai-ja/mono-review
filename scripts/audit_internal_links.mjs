import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import matter from "gray-matter";

const postsDirectory = path.resolve("src/content/posts");
const strict = process.argv.includes("--strict");

const listMarkdownFiles = async (directory) => {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map((entry) => {
      const fullPath = path.join(directory, entry.name);
      return entry.isDirectory() ? listMarkdownFiles(fullPath) : [fullPath];
    }),
  );
  return nested.flat().filter((file) => /\.mdx?$/i.test(file));
};

const normalizeSlug = (value) => {
  const normalized = String(value ?? "")
    .trim()
    .replace(/^https?:\/\/(?:www\.)?monoslog\.com/i, "")
    .replace(/^\/?blog\//, "")
    .replace(/[?#].*$/, "")
    .replace(/\/$/, "");
  try {
    return decodeURIComponent(normalized);
  } catch {
    return normalized;
  }
};

const extractBodyLinks = (body) => {
  const links = new Set();
  const patterns = [
    /\]\(\s*(?:https?:\/\/(?:www\.)?monoslog\.com)?\/blog\/([^\s)"'#?]+)[^)]*\)/gi,
    /href=["'](?:https?:\/\/(?:www\.)?monoslog\.com)?\/blog\/([^"'#?]+)[^"']*["']/gi,
  ];
  for (const pattern of patterns) {
    for (const match of body.matchAll(pattern)) {
      const slug = normalizeSlug(match[1]);
      if (slug) links.add(slug);
    }
  }
  return links;
};

const files = await listMarkdownFiles(postsDirectory);
const posts = await Promise.all(
  files.map(async (file) => {
    const source = await readFile(file, "utf8");
    const { data, content } = matter(source);
    const fileSlug = path.basename(file).replace(/\.mdx?$/i, "");
    const slug = normalizeSlug(data.slug || fileSlug);
    const relatedPosts = Array.isArray(data.relatedPosts)
      ? data.relatedPosts.map(normalizeSlug).filter(Boolean)
      : [];
    return {
      file: path.relative(process.cwd(), file),
      slug,
      draft: data.draft === true,
      references: new Set([...relatedPosts, ...extractBodyLinks(content)]),
    };
  }),
);

const knownSlugs = new Set(posts.map((post) => post.slug));
const publishedPosts = posts.filter((post) => !post.draft);
const inbound = new Map(publishedPosts.map((post) => [post.slug, new Set()]));
const broken = [];

for (const post of publishedPosts) {
  for (const reference of post.references) {
    if (!knownSlugs.has(reference)) {
      broken.push({ source: post.slug, target: reference, file: post.file });
      continue;
    }
    if (reference !== post.slug && inbound.has(reference)) {
      inbound.get(reference).add(post.slug);
    }
  }
}

const orphaned = publishedPosts
  .filter((post) => inbound.get(post.slug)?.size === 0)
  .map((post) => post.slug)
  .sort();

console.log(`Published posts: ${publishedPosts.length}`);
console.log(`Broken internal references: ${broken.length}`);
for (const item of broken) {
  console.log(`  ${item.source} -> ${item.target} (${item.file})`);
}
console.log(`Posts without editorial inbound links: ${orphaned.length}`);
for (const slug of orphaned) console.log(`  ${slug}`);

if (broken.length > 0 || (strict && orphaned.length > 0)) {
  process.exitCode = 1;
}
