const DEFAULT_SCOPE = "repo";
const MAX_STATE_AGE_SECONDS = 10 * 60;

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function html(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function base64UrlEncode(input) {
  const bytes = typeof input === "string" ? new TextEncoder().encode(input) : input;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(input) {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((input.length + 3) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

async function hmac(value, secret) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value));
  return base64UrlEncode(new Uint8Array(signature));
}

async function makeState(payload, secret) {
  const encoded = base64UrlEncode(JSON.stringify(payload));
  const signature = await hmac(encoded, secret);
  return `${encoded}.${signature}`;
}

async function readState(state, secret) {
  const [encoded, signature] = state.split(".");
  if (!encoded || !signature) throw new Error("Invalid OAuth state.");

  const expected = await hmac(encoded, secret);
  if (signature !== expected) throw new Error("OAuth state signature mismatch.");

  const payload = JSON.parse(base64UrlDecode(encoded));
  const age = Math.floor(Date.now() / 1000) - Number(payload.iat || 0);
  if (age < 0 || age > MAX_STATE_AGE_SECONDS) throw new Error("OAuth state expired.");
  return payload;
}

function getAllowedOrigins(env) {
  return String(env.ALLOWED_ORIGINS || env.ALLOWED_ORIGIN || "https://monoslog.com")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
}

function isAllowedOrigin(origin, env) {
  return getAllowedOrigins(env).includes(origin);
}

function requireEnv(env, name) {
  const value = env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

function authError(message, status = 400) {
  return html(`<!doctype html><meta charset="utf-8"><title>OAuth Error</title><h1>OAuth Error</h1><p>${escapeHtml(message)}</p>`, status);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function handleAuth(request, env) {
  const url = new URL(request.url);
  const origin = url.searchParams.get("origin") || url.searchParams.get("site") || env.DEFAULT_SITE_ORIGIN || "https://monoslog.com";

  if (!isAllowedOrigin(origin, env)) {
    return authError(`Origin is not allowed: ${origin}`, 403);
  }

  const clientId = requireEnv(env, "GITHUB_CLIENT_ID");
  const stateSecret = env.OAUTH_STATE_SECRET || requireEnv(env, "GITHUB_CLIENT_SECRET");
  const redirectUri = env.OAUTH_REDIRECT_URI || `${url.origin}/callback`;
  const scope = env.GITHUB_OAUTH_SCOPE || DEFAULT_SCOPE;

  const state = await makeState(
    {
      provider: "github",
      origin,
      iat: Math.floor(Date.now() / 1000),
      nonce: crypto.randomUUID(),
    },
    stateSecret,
  );

  const authUrl = new URL("https://github.com/login/oauth/authorize");
  authUrl.searchParams.set("client_id", clientId);
  authUrl.searchParams.set("redirect_uri", redirectUri);
  authUrl.searchParams.set("scope", scope);
  authUrl.searchParams.set("state", state);

  return Response.redirect(authUrl.toString(), 302);
}

async function handleCallback(request, env) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  if (error) return authError(`${error}: ${url.searchParams.get("error_description") || "GitHub authorization failed."}`, 400);
  if (!code || !state) return authError("Missing OAuth code or state.", 400);

  const clientId = requireEnv(env, "GITHUB_CLIENT_ID");
  const clientSecret = requireEnv(env, "GITHUB_CLIENT_SECRET");
  const stateSecret = env.OAUTH_STATE_SECRET || clientSecret;
  const payload = await readState(state, stateSecret);
  const targetOrigin = payload.origin || env.DEFAULT_SITE_ORIGIN || "https://monoslog.com";

  if (!isAllowedOrigin(targetOrigin, env)) {
    return authError(`Origin is not allowed: ${targetOrigin}`, 403);
  }

  const redirectUri = env.OAUTH_REDIRECT_URI || `${url.origin}/callback`;
  const tokenResponse = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
      "user-agent": "monoslog-decap-oauth-worker",
    },
    body: JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
      code,
      redirect_uri: redirectUri,
    }),
  });

  const tokenData = await tokenResponse.json();
  if (!tokenResponse.ok || tokenData.error || !tokenData.access_token) {
    return authError(tokenData.error_description || tokenData.error || "Failed to exchange GitHub OAuth token.", 502);
  }

  const message = `authorization:github:success:${JSON.stringify({ token: tokenData.access_token, provider: "github" })}`;
  const safeTargetOrigin = JSON.stringify(targetOrigin);
  const safeMessage = JSON.stringify(message);

  return html(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Decap CMS Authorization</title>
  </head>
  <body>
    <p>Authorization complete. You can close this window.</p>
    <script>
      (function () {
        var targetOrigin = ${safeTargetOrigin};
        var message = ${safeMessage};

        function sendAuthorization(event) {
          if (event && event.origin !== targetOrigin) return;
          if (window.opener) {
            window.opener.postMessage(message, targetOrigin);
          }
        }

        window.addEventListener("message", sendAuthorization, false);
        if (window.opener) {
          window.opener.postMessage("authorizing:github", targetOrigin);
          setTimeout(function () { sendAuthorization({ origin: targetOrigin }); }, 500);
          setTimeout(function () { window.close(); }, 1500);
        }
      })();
    </script>
  </body>
</html>`);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": env.DEFAULT_SITE_ORIGIN || "https://monoslog.com",
          "access-control-allow-methods": "GET, OPTIONS",
          "access-control-allow-headers": "content-type",
        },
      });
    }

    try {
      if (url.pathname === "/" || url.pathname === "/health") {
        return json({ ok: true, service: "monoslog-decap-oauth" });
      }
      if (url.pathname === "/auth") return handleAuth(request, env);
      if (url.pathname === "/callback") return handleCallback(request, env);
      return json({ error: "Not found" }, 404);
    } catch (error) {
      return authError(error.message || "Unexpected OAuth proxy error.", 500);
    }
  },
};