import Fuse from "fuse.js";
import { useEffect, useMemo, useState } from "react";

type SearchItem = {
  slug: string;
  title: string;
  description: string;
  categories: string[];
  tags: string[];
  content: string;
};

type Props = {
  searchList: SearchItem[];
};

const SearchBar = ({ searchList }: Props) => {
  const [query, setQuery] = useState("");

  useEffect(() => {
    setQuery(new URLSearchParams(window.location.search).get("key")?.trim() ?? "");
  }, []);

  const fuse = useMemo(
    () =>
      new Fuse(searchList, {
        keys: [
          { name: "title", weight: 0.45 },
          { name: "description", weight: 0.2 },
          { name: "categories", weight: 0.15 },
          { name: "tags", weight: 0.15 },
          { name: "content", weight: 0.05 },
        ],
        threshold: 0.35,
        ignoreLocation: true,
      }),
    [searchList],
  );

  const normalizedQuery = query.trim();
  const results = useMemo(
    () => normalizedQuery ? fuse.search(normalizedQuery, { limit: 20 }).map(({ item }) => item) : [],
    [fuse, normalizedQuery],
  );

  const syncSearchUrl = () => {
    const url = new URL(window.location.href);
    if (normalizedQuery) url.searchParams.set("key", normalizedQuery);
    else url.searchParams.delete("key");
    window.history.replaceState({}, "", url);
  };

  return (
    <div>
      <header className="mb-8 text-center">
        <h1 className="h2 mb-3">サイト内検索</h1>
        <p className="text-text">記事名、カテゴリ、製品名などを入力してください。</p>
      </header>

      <form
        className="mb-10 flex flex-col gap-3 sm:flex-row"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          syncSearchUrl();
        }}
      >
        <label className="sr-only" htmlFor="site-search-input">検索キーワード</label>
        <input
          id="site-search-input"
          className="form-input min-w-0 flex-1 rounded-md border border-border bg-white px-4 py-3 text-dark focus:border-primary focus:outline-none"
          type="search"
          name="key"
          placeholder="例：Echo Dot、モバイルWiFi"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
        />
        <button className="btn btn-primary shrink-0 px-7 py-3" type="submit">
          検索
        </button>
      </form>

      <div aria-live="polite">
        {!normalizedQuery ? (
          <p className="rounded-md border border-border bg-light px-5 py-4 text-center text-text">
            検索キーワードを入力すると、該当する記事が表示されます。
          </p>
        ) : results.length > 0 ? (
          <>
            <p className="mb-5 text-sm text-text">
              「{normalizedQuery}」の検索結果：{results.length}件
            </p>
            <ul className="divide-y divide-border border-y border-border">
              {results.map((item) => (
                <li key={item.slug} className="py-6">
                  <a className="group block" href={`/blog/${item.slug}/`}>
                    <h2 className="h5 mb-2 transition group-hover:text-primary">{item.title}</h2>
                    <p className="mb-3 text-sm leading-relaxed text-text">{item.description}</p>
                    {(item.categories.length > 0 || item.tags.length > 0) && (
                      <p className="text-xs text-text-light">
                        {[...item.categories, ...item.tags].slice(0, 5).join(" / ")}
                      </p>
                    )}
                  </a>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="rounded-md border border-border bg-light px-5 py-4 text-center text-text">
            「{normalizedQuery}」に一致する記事は見つかりませんでした。
          </p>
        )}
      </div>
    </div>
  );
};

export default SearchBar;
