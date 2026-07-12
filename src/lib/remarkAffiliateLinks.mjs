const merchantForHref = (href) => {
  try {
    const url = new URL(href, "https://monoslog.com");
    const host = url.hostname.toLowerCase();
    if (host === "amzn.to" || host.endsWith("amazon.co.jp")) return "amazon";
    if (host.endsWith("rakuten.co.jp") || host === "a.r10.to") return "rakuten";
    if (host.endsWith("yahoo.co.jp")) return "yahoo";
    if (url.hostname === "monoslog.com" && url.pathname.startsWith("/go/")) {
      return "redirect";
    }
  } catch {
    return "";
  }
  return "";
};

const visit = (node) => {
  if (!node || typeof node !== "object") return;

  if (node.type === "link" && typeof node.url === "string") {
    const merchant = merchantForHref(node.url);
    if (merchant) {
      node.data ??= {};
      node.data.hProperties ??= {};
      Object.assign(node.data.hProperties, {
        rel: "sponsored nofollow noopener noreferrer",
        target: "_blank",
        "data-affiliate-link": "",
        "data-affiliate-merchant": merchant,
        "data-affiliate-slot-id": "inline",
      });
    }
  }

  if (Array.isArray(node.children)) {
    node.children.forEach(visit);
  }
};

export default function remarkAffiliateLinks() {
  return (tree) => visit(tree);
}
