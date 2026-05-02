/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly MICROCMS_SERVICE_DOMAIN?: string;
  readonly MICROCMS_API_KEY?: string;
  readonly MICROCMS_API_ORIGIN?: string;
  /** Content API の記事エンドポイント名（既定: `blogs`） */
  readonly MICROCMS_POSTS_ENDPOINT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
