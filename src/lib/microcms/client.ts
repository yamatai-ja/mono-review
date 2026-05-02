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

export function microCMSConfigFromEnv(env: {
  MICROCMS_SERVICE_DOMAIN?: string;
  MICROCMS_API_KEY?: string;
  MICROCMS_API_ORIGIN?: string;
}): MicroCMSClientConfig {
  const serviceDomain = env.MICROCMS_SERVICE_DOMAIN;
  const apiKey = env.MICROCMS_API_KEY;
  if (!serviceDomain || !apiKey) {
    throw new Error(
      "MICROCMS_SERVICE_DOMAIN と MICROCMS_API_KEY を環境変数に設定してください。",
    );
  }
  return {
    serviceDomain,
    apiKey,
    origin: env.MICROCMS_API_ORIGIN,
  };
}