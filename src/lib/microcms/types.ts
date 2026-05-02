/**
 * microCMS が付与する共通フィールド（リスト・詳細レスポンス）
 * @see https://document.microcms.io/content-api/get-list-contents
 */
export type MicroCMSMetaFields = {
  id: string;
  createdAt: string;
  updatedAt: string;
  publishedAt: string;
  revisedAt: string;
};

export type MicroCMSContent<T extends Record<string, unknown>> = T &
  MicroCMSMetaFields;

export type MicroCMSListResponse<T> = {
  contents: T[];
  totalCount: number;
  offset: number;
  limit: number;
};

export type MicroCMSClientConfig = {
  /** 管理画面 URL のサブドメイン（例: `my-site` → `https://my-site.microcms.io`） */
  serviceDomain: string;
  /** Content API キー（サーバー側でのみ使用し、クライアントに公開しない） */
  apiKey: string;
  /** デフォルト `https`。オンプレミス等で変更する場合のみ指定 */
  origin?: string;
};

/** `getList` / `getDetail` に渡すクエリ（値は URL クエリ文字列に変換される） */
export type MicroCMSQuery = Record<
  string,
  string | number | boolean | undefined
>;
