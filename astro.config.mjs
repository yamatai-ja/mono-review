import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import AutoImport from "astro-auto-import";
import gtm from "astro-gtm-lite";
import { defineConfig, fontProviders, sharpImageService } from "astro/config";
import config from "./src/config/config.json";
import theme from "./src/config/theme.json";

function parseEnvFile(filePath) {
  if (!existsSync(filePath)) return {};
  const out = {};
  const text = readFileSync(filePath, "utf8");
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq <= 0) continue;
    const k = t.slice(0, eq).trim();
    if (!k) continue;
    let v = t.slice(eq + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    out[k] = v;
  }
  return out;
}

function dotEnvForMode(mode) {
  const root = process.cwd();
  return {
    ...parseEnvFile(resolve(root, ".env")),
    ...parseEnvFile(resolve(root, ".env.local")),
    ...parseEnvFile(resolve(root, `.env.${mode}`)),
    ...parseEnvFile(resolve(root, `.env.${mode}.local`)),
  };
}

// Helper to parse font string format: "FontName:wght@400;500;600;700"
function parseFontString(fontStr) {
  const [name, weightPart] = fontStr.split(":");
  let weights = [400]; // default weight

  if (weightPart) {
    // Extract weights from wght@400;500;600 format
    const weightMatch = weightPart.match(/wght@?([\d;]+)/);
    if (weightMatch) {
      weights = weightMatch[1].split(";").map((w) => parseInt(w, 10));
    }
  }

  // remove + from font name and add space
  const cleanName = name.replace(/\+/g, " ");
  return { name: cleanName, weights };
}

// Build fonts configuration from theme.json
const fontsConfig = Object.entries(theme.fonts.font_family)
  .filter(([key]) => !key.includes("_type")) // Filter out type entries
  .map(([key, fontStr]) => {
    const { name, weights } = parseFontString(fontStr);
    const typeKey = `${key}_type`;
    const fallback = theme.fonts.font_family[typeKey] || "sans-serif";

    return {
      name,
      cssVariable: `--font-${key}`,
      provider: fontProviders.google(),
      weights,
      display: "swap",
      fallbacks: [fallback],
    };
  });

// https://astro.build/config
export default defineConfig(({ mode }) => {
  const fromFile = dotEnvForMode(mode);
  const micro = (key) =>
    JSON.stringify(process.env[key] ?? fromFile[key] ?? "");

  return {
    site: config.site.base_url ? config.site.base_url : "http://examplesite.com",
    base: config.site.base_path ? config.site.base_path : "/",
    trailingSlash: config.site.trailing_slash ? "always" : "never",
    image: {
      service: sharpImageService(),
      remotePatterns: [
        {
          protocol: "https",
          hostname: "images.microcms-assets.io",
          pathname: "/**",
        },
      ],
    },
    vite: {
      plugins: [tailwindcss()],
      define: {
        "import.meta.env.MICROCMS_SERVICE_DOMAIN": micro("MICROCMS_SERVICE_DOMAIN"),
        "import.meta.env.MICROCMS_API_KEY": micro("MICROCMS_API_KEY"),
        "import.meta.env.MICROCMS_API_ORIGIN": micro("MICROCMS_API_ORIGIN"),
        "import.meta.env.MICROCMS_POSTS_ENDPOINT": JSON.stringify("blogs"),
      },
    },
    fonts: fontsConfig,
    integrations: [
      react(),
      sitemap(),
      AutoImport({
        imports: [
          "@/shortcodes/Button",
          "@/shortcodes/Accordion",
          "@/shortcodes/Notice",
          "@/shortcodes/Video",
          "@/shortcodes/Youtube",
          "@/shortcodes/Tabs",
          "@/shortcodes/Tab",
        ],
      }),
      mdx(),
      gtm({
        enable: config.google_tag_manager.enable,
        id: config.google_tag_manager.gtm_id,
        devMode: true,
      }),
    ],
    markdown: {
      shikiConfig: { theme: "one-dark-pro", wrap: true },
    },
  };
});
