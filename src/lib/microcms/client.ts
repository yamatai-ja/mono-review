import type {
  MicroCMSClientConfig,
  MicroCMSContent,
  MicroCMSListResponse,
  MicroCMSQuery,
} from "./types";

function buildSearchParams(query?: MicroCMSQuery): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue;
    params.set(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

/** `https://{service}.microcms.io/api/v1` */
function resolveApiBase(config: MicroCMSClientConfig): string {
  let host = config.serviceDomain.trim().replace(/^https?:\/\//, "");
  if (!host.endsWith(".microcms.io")) {
    host = `${host}.microcms.io`;
  }
  const origin = (config.origin ?? `https://${host}`).replace(/\/$/, "");
  return `${origin}/api/v1`;
}

export type MicroCMSClient = {
  getList<T extends Record<string, unknown>>(
    endpoint: string,
    query?: MicroCMSQuery,
  ): Promise<MicroCMSListResponse<MicroCMSContent<T>>>;

  getDetail<T extends Record<string, unknown>>(
    endpoint: string,
    contentId: string,
    query?: MicroCMSQuery,
  ): Promise<MicroCMSContent<T>>;

  getObject<T extends Record<string, unknown>>(
    endpoint: string,
    query?: MicroCMSQuery,
  ): Promise<MicroCMSContent<T>>;

  getAllContents<T extends Record<string, unknown>>(
    endpoint: string,
    options?: MicroCMSQuery & { pageSize?: number },
  ): Promise<MicroCMSContent<T>[]>;
};

async function microCMSFetch<T>(
  config: MicroCMSClientConfig,
  path: string,
): Promise<T> {
  const base = resolveApiBase(config);
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;

  const res = await fetch(url, {
    headers: {
      "X-MICROCMS-API-KEY": config.apiKey,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `microCMS request failed: ${res.status} ${res.statusText} — ${body}`,
    );
  }

  return res.json() as Promise<T>;
}

/**
 * microCMS Content API クライアントを生成する。
 *
 * 環境変数例（`.env`）: `MICROCMS_SERVICE_DOMAIN`, `MICROCMS_API_KEY`
 */
export function createMicroCMSClient(
  config: MicroCMSClientConfig,
): MicroCMSClient {
  return {
    getList: async <T extends Record<string, unknown>>(
      endpoint: string,
      query?: MicroCMSQuery,
    ): Promise<MicroCMSListResponse<MicroCMSContent<T>>> => {
      const q = buildSearchParams(query);
      return microCMSFetch(
        config,
        `/${encodeURIComponent(endpoint)}${q}`,
      ) as Promise<MicroCMSListResponse<MicroCMSContent<T>>>;
    },

    getDetail: async <T extends Record<string, unknown>>(
      endpoint: string,
      contentId: string,
      query?: MicroCMSQuery,
    ): Promise<MicroCMSContent<T>> => {
      const q = buildSearchParams(query);
      return microCMSFetch(
        config,
        `/${encodeURIComponent(endpoint)}/${encodeURIComponent(contentId)}${q}`,
      ) as Promise<MicroCMSContent<T>>;
    },

    getObject: async <T extends Record<string, unknown>>(
      endpoint: string,
      query?: MicroCMSQuery,
    ): Promise<MicroCMSContent<T>> => {
      const q = buildSearchParams(query);
      return microCMSFetch(
        config,
        `/${encodeURIComponent(endpoint)}${q}`,
      ) as Promise<MicroCMSContent<T>>;
    },

    getAllContents: async <T extends Record<string, unknown>>(
      endpoint: string,
      options?: MicroCMSQuery & { pageSize?: number },
    ): Promise<MicroCMSContent<T>[]> => {
      const pageSize = options?.pageSize ?? 100;
      const { pageSize: _p, ...rest } = options ?? {};
      const out: MicroCMSContent<T>[] = [];
      let offset = 0;
      let total = Infinity;

      while (offset < total) {
        const list = await microCMSFetch<
          MicroCMSListResponse<MicroCMSContent<T>>
        >(
          config,
          `/${encodeURIComponent(endpoint)}${buildSearchParams({
            ...rest,
            limit: pageSize,
            offset,
          })}`,
        );
        out.push(...list.contents);
        total = list.totalCount;
        offset += list.contents.length;
        if (list.contents.length === 0) break;
      }

      return out;
    },
  };
}

/** microCMS の API でのコンテンツ名（未設定時は `blogs`） */
export const MICROCMS_POSTS_ENDPOINT_DEFAULT = "blogs";

function processEnvFallback(): Partial<
  Pick<
    NodeJS.ProcessEnv,
    | "MICROCMS_SERVICE_DOMAIN"
    | "MICROCMS_API_KEY"
    | "MICROCMS_API_ORIGIN"
    | "MICROCMS_POSTS_ENDPOINT"
  >
> {
  if (typeof globalThis.process === "undefined" || !globalThis.process?.env)
    return {};
  return globalThis.process.env;
}

/** posts コンテンツの API キー（`MICROCMS_POSTS_ENDPOINT`）。CI では `process.env` 側だけに載る場合あり。 */
export function microCMSPostsEndpoint(env: {
  MICROCMS_POSTS_ENDPOINT?: string;
}): string {
  const pe = processEnvFallback();
  return (
    env.MICROCMS_POSTS_ENDPOINT?.trim() ||
    pe.MICROCMS_POSTS_ENDPOINT?.trim() ||
    MICROCMS_POSTS_ENDPOINT_DEFAULT
  );
}

const MICROCMS_SERVICE_DOMAIN_DEFAULT = "9dpfhv920t";
const MICROCMS_API_KEY_DEFAULT = "R0QVtPegFalIVWnBlrpV8VPWkYHqfqNFcp4o";

/** `import.meta.env` に載らない CI 環境変数は `process.env` から読む。 */
export function microCMSConfigFromEnv(env: {
  MICROCMS_SERVICE_DOMAIN?: string;
  MICROCMS_API_KEY?: string;
  MICROCMS_API_ORIGIN?: string;
}): MicroCMSClientConfig {
  const pe = processEnvFallback();
  const serviceDomain = (env.MICROCMS_SERVICE_DOMAIN || pe.MICROCMS_SERVICE_DOMAIN || MICROCMS_SERVICE_DOMAIN_DEFAULT).trim();
  const apiKey = (env.MICROCMS_API_KEY || pe.MICROCMS_API_KEY || MICROCMS_API_KEY_DEFAULT).trim();
  if (!serviceDomain || !apiKey) {
    throw new Error(
      "MICROCMS_SERVICE_DOMAIN と MICROCMS_API_KEY を環境変数に設定してください。",
    );
  }
  return {
    serviceDomain,
    apiKey,
    origin: env.MICROCMS_API_ORIGIN ?? pe.MICROCMS_API_ORIGIN,
  };
}