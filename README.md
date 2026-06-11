<h1 align=center>Bookworm Light Astro</h1>
<p align=center>Bookworm Light is a feature-rich, minimal, highly customizable, easy-to-use free Astro blog theme.</p>
<h2 align="center"> <a target="_blank" href="https://bookworm-light-astro.vercel.app/" rel="nofollow">👀Demo</a> | <a  target="_blank" href="https://pagespeed.web.dev/report?url=https%3A%2F%2Fbookworm-light-astro.vercel.app%2F&form_factor=desktop">Page Speed (100%)🚀</a>
</h2>

<p align=center>
  <a href="https://github.com/withastro/astro/releases/tag/astro%406.1.9" alt="Contributors">
    <img src="https://img.shields.io/static/v1?label=ASTRO&message=6.1.9&color=000&logo=astro" />
  </a>

  <a href="https://github.com/themefisher/bookworm-light-astro/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/themefisher/bookworm-light-astro" alt="license"></a>

  <img src="https://img.shields.io/github/languages/code-size/themefisher/bookworm-light-astro" alt="code size">

  <a href="https://github.com/themefisher/bookworm-light-astro/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/themefisher/bigspring-light-astro" alt="contributors"></a>
</p>

![bookworm-light](https://assets.teamosis.com/thumbs/bookworm-light.png)

Bookworm Light is a minimal multi-author free Astro blog theme which is perfect for any kind of blog website. Whether you're interested in food, beauty, travel, photography, lifestyle, fitness, health, or other topics, this theme is a great fit. The theme is super fast and SEO friendly which makes it easier for your content to be discovered by search engines.

## 🔑Key Features

- 🎨 Highly Customizable (Color, Font, Menu, Social Links, SEO Meta Tags, etc.)
- 👥 Multi-Author Support
- 📚 Authors Page
- 👤 Author Single Page
- 🔍 Search Functionality with FuseJS
- 🏷️ Tags and Categories Support
- 📲 Post Social Share Option
- 🔗 Similar Post Suggestions
- ⚡ Fast by Default (95+ Google PageSpeed Score)
- ⚙️ Netlify Settings Pre-configured
- 📬 Contact Form Support
- 🌅 Support OG Image
- ✍️ Write and Update Content in Markdown / MDX
- 📚 MDX Components Auto Import
- 📝 Includes Draft Pages and Posts
- 🚀 Built with Tailwind CSS Framework
- 📱 Fully Responsive on Desktops, Tablets, and Smartphones
- 🔍 SEO Friendly

<!-- installation -->

## 🔧Installation

After downloading the template, you have some prerequisites to install. Then you can run it on your localhost. You can view the package.json file to see which scripts are included.

### ⚙️Install prerequisites (once for a machine)

- **Node Installation:** [Install node js](https://nodejs.org/en/download/) [Recommended LTS version]

### 🖥️Local setup

After successfully installing those dependencies, open this template with any IDE [[VS Code](https://code.visualstudio.com/) recommended], and then open the integrated terminal in your editor [VS Code shortcut <code>ctrl/cmd+\`</code>]

- Install dependencies

```
yarn install
```

- Run locally

```
yarn dev
```

After that, it will open up a preview of the template in your default browser, watch for changes to source files, and live-reload the browser when changes are saved.

## 🔨Production Build

After finishing all the customization, you can create a production build by running this command.

```
yarn build
```

<!-- edit with sitepins -->

## 📝 Edit Content with CMS

This template comes pre-configured with [**Sitepins**](https://sitepins.com/?aff=tfgithub), a Git-based Headless CMS designed for seamless content management. You can update your website’s text, images, and configuration without touching a single line of code.

**How to get started:**

Click the Edit with Sitepins button below and follow the on-screen instructions to start editing your content visually.

  <a target="_blank" href="https://app.sitepins.com/new/clone?name=Bookworm%20Light%20Astro&repository=https://github.com/themefisher/bookworm-light-astro/?aff=tfgithub">
    <img src="https://sitepins.com/button.svg" alt="Edit with Sitepins">
  </a>
  
<!-- reporting issue -->

## 🐞Reporting Issues

We use GitHub Issues as the official bug tracker for this Template. Please Search [existing issues](https://github.com/themefisher/bookworm-light-astro/issues). It’s possible someone has already reported the same problem.
If your problem or idea has not been addressed yet, feel free to [open a new issue](https://github.com/themefisher/bookworm-light-astro/issues).

<!-- licence -->

## 📄License

Copyright (c) 2023 - Present, Designed & Developed by [Themefisher](https://themefisher.com)

**Code License:** Released under the [MIT](https://github.com/themefisher/bookworm-light-astro/blob/main/LICENSE) license.

**Image license:** The images are only for demonstration purposes. They have their license, we don't have permission to share those images.

## 👨‍💻Need Custom Development Services?

Besides developing beautifully designed and blazing-fast themes, we help businesses create fast, performance-focused, scalable & secure websites based on NextJs, Hugo, Astro, etc.

If you need a custom theme, theme customization, or complete website development services from scratch you can [Hire Us](https://themefisher.com/contact).

## Decap CMS

This site includes a Decap CMS admin screen for editing Markdown posts in `src/content/posts`.

Files:

- `public/admin/index.html`
- `public/admin/config.yml`

Local editing flow:

```bash
npm run cms:local
npm run dev
```

Then open:

```text
http://localhost:4321/admin/
```

The CMS edits the Astro `posts` collection frontmatter fields, including `title`, `description`, `date`, `categories`, `tags`, `products`, and `draft`.

Production note: the config uses the GitHub backend for `yamatai-ja/mono-review`. To edit from the deployed `/admin/` page, configure GitHub OAuth for Decap CMS or a compatible auth proxy. Local editing works with `local_backend: true`.
## Content Sync Policy

This project treats Astro Markdown files in `src/content/posts` as the normal editing source for Decap CMS.

Use these commands for day-to-day editing:

```bash
npm run dev
npm run cms:local
```

microCMS import is intentionally manual so Decap CMS edits are not overwritten during local development or production builds.

Run this only when you explicitly want to import posts from microCMS:

```bash
npm run sync:microcms
```

If you want to import from microCMS and then build immediately:

```bash
npm run build:microcms
```
## Publishing Flow

The normal publishing source is the Astro Markdown collection in `src/content/posts`.

Recommended flow:

```text
Decap CMS or Codex edits Markdown
-> commit to GitHub main
-> GitHub Actions runs npm run build
-> GitHub Pages publishes https://monoslog.com
```

Local editing:

```bash
npm run dev
npm run cms:local
```

Open:

```text
http://127.0.0.1:4321/admin/
```

Production editing:

```text
https://monoslog.com/admin/
```

The production admin screen uses the GitHub backend configured in `public/admin/config.yml`:

```yaml
backend:
  name: github
  repo: yamatai-ja/mono-review
  branch: main
```

To save from the deployed CMS, configure a Decap CMS compatible GitHub OAuth provider/auth proxy for `https://monoslog.com/admin/`. Local editing does not need OAuth because it uses `local_backend: true` and `npm run cms:local`.

Do not run microCMS import during normal editing. It is manual only:

```bash
npm run sync:microcms
```

Use it only when you intentionally want to overwrite/import Markdown from microCMS.
## Decap CMS GitHub OAuth Proxy

Production Decap CMS login at `https://monoslog.com/admin/` uses a Cloudflare Worker OAuth proxy.

Worker files:

- `workers/decap-oauth/index.js`
- `workers/decap-oauth/wrangler.jsonc`

Decap config:

```yaml
backend:
  name: github
  repo: yamatai-ja/mono-review
  branch: main
  base_url: https://decap-oauth.monoslog.com
  auth_endpoint: auth
```

### 1. Create a GitHub OAuth App

Create it from GitHub Developer settings.

Recommended values:

```text
Application name: Monoslog Decap CMS
Homepage URL: https://monoslog.com/admin/
Authorization callback URL: https://decap-oauth.monoslog.com/callback
```

Copy the Client ID and Client Secret.

### 2. Register Cloudflare Worker secrets

```bash
npm run oauth:secret:client-id
npm run oauth:secret:client-secret
npm run oauth:secret:state
```

Use a long random value for `OAUTH_STATE_SECRET`.

### 3. Deploy the OAuth Worker

```bash
npm run oauth:deploy
```

The Worker is configured for the custom domain:

```text
https://decap-oauth.monoslog.com
```

Make sure the custom domain exists in Cloudflare Workers routes/custom domains.

### 4. Test production CMS login

Open:

```text
https://monoslog.com/admin/
```

Click GitHub login. After authorization, Decap CMS can commit Markdown edits to `yamatai-ja/mono-review` on `main`. GitHub Pages then publishes the site automatically.

Notes:

- The GitHub user must have write permission to `yamatai-ja/mono-review`.
- The Worker scope defaults to `repo` so it works for both public and private repositories. You can change `GITHUB_OAUTH_SCOPE` in `workers/decap-oauth/wrangler.jsonc` if needed.
- Local editing still works without GitHub OAuth by running `npm run dev` and `npm run cms:local`.
