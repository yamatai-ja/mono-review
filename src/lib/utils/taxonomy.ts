import { slugify } from "@/lib/utils/textConverter";

export type TaxonomyTerm = {
  id: string;
  name: string;
};

export const toTaxonomyTerm = (value: unknown): TaxonomyTerm => {
  if (typeof value === "object" && value !== null) {
    const term = value as { id?: string; name?: string };
    return {
      id: String(term.id || slugify(term.name || "")).trim(),
      name: String(term.name || term.id || "").trim(),
    };
  }

  return {
    id: slugify(String(value)),
    name: String(value).trim(),
  };
};
