# Daumenkino

A film journal for Ann-Sophie & Rafael. Short reviews on cinematic backdrops, a podcast link, and each host’s four most recently watched films. Built for GitHub Pages and the future custom domain **daumenkino.fm**.

## Local development

Only Python 3.10+ is required. No npm installation or frontend framework.

```sh
python3 scripts/sync.py     # Update both public Letterboxd feeds (optional when working offline)
python3 scripts/build.py    # Generate dist/ from the saved snapshot
python3 -m http.server 4173 --directory dist
```

Open http://localhost:4173. After editing `index.html`, `styles.css`, `app.js`, or the build script, run the build again and reload. `index.html` is a template; serve `dist/`, not the repository root.

```sh
python3 -m unittest discover -s tests -v
```

## Publishing and automatic updates

The `Sync Letterboxd and publish` workflow runs on pushes to `main`, manually in Actions, and approximately every six hours. It reads `hejrafa` and `annso` public RSS feeds, stores the snapshot, builds static HTML, and deploys to GitHub Pages. GitHub schedules can be delayed; scheduled runs in inactive public repositories may be disabled after 60 days. Re-enable the workflow if necessary.

GitHub Settings → Pages → Source must be **GitHub Actions**. No browser-side feed requests or CORS proxy are needed. The whole page is generated HTML, with small JavaScript enhancements for filtering and showing more reviews. If a feed temporarily fails, its saved content is retained. If no saved data exists for an account, the build fails rather than publishing a misleading empty page.

The overview alternates between the two authors. Filters show each author's reviews in watched-date order. Cards use the first two sentences, with a 180-character cap, and link to the original full review. Original wording is preserved. Spoiler-marked reviews are not quoted. The footer uses the newest four distinct films with a diary watched date, including entries without reviews. RSS is a rolling recent-activity window, not the entire Letterboxd history; snapshots preserve previously fetched entries. Historical edits/deletions outside that window require updating the saved snapshot manually.

## TMDB backdrops

Add your **TMDB API Read Access Token** to repository Settings → Secrets and variables → Actions as `TMDB_READ_TOKEN`, then run the workflow. Do not paste the token into source files. The API resolves films by the TMDB ID in Letterboxd RSS, avoiding ambiguous title searches. Without the token, the site uses public Letterboxd film-page backdrops where available, then the RSS poster as a fallback. Images stay on their original CDNs. The cache avoids repeatedly fetching already resolved images. To migrate a cached Letterboxd backdrop to TMDB, clear that entry's `backdrop` field and rerun with the token.

TMDB documentation: https://developer.themoviedb.org/docs/getting-started and https://developer.themoviedb.org/docs/image-basics. Film images belong to their respective rights holders. Fonts are self-hosted with their SIL Open Font Licenses in `assets/fonts/`.

## Custom domain: daumenkino.fm

The initial site uses https://hejrafa.github.io/Daumenkino/ so the draft stays accessible before domain setup. All asset links are relative and work at both addresses. No custom domain is enabled yet.

1. At your DNS provider, point the apex domain to GitHub Pages using the records in GitHub’s current documentation: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site.
2. Optionally point `www` to `hejrafa.github.io` using a CNAME record.
3. Set `daumenkino.fm` in this repository’s Settings → Pages → Custom domain.
4. Once DNS checks and the certificate finish, enable **Enforce HTTPS**.
5. Verify domain ownership using the TXT record GitHub provides in your account’s Pages settings.

No DNS settings are changed by this repository. For an Actions deployment, configure the custom domain in Pages settings; GitHub does not require a deployed CNAME file.

## Content and layout

- `index.html`: German page copy, podcast and Instagram URLs, layout template.
- `styles.css`: responsive visual design, self-hosted typography, reduced-motion behavior.
- `app.js`: author filters, progressive review loading.
- `scripts/sync.py`: RSS import and image enrichment, server-side only.
- `scripts/build.py`: safely escaped static rendering.
- `data/letterboxd.json`: committed source snapshot and growing review archive.

Podcast links currently open the existing show/archive. No new short audio episodes are invented or connected to reviews. Per-film audio can be added once those episodes exist.
