# Development and publishing

Technical notes for maintaining the [Daumenkino website](../README.md). Run the commands below from the repository root.

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
node --test tests/flipbook.test.cjs # Optional locally; Node is available in GitHub Actions
```

## Publishing and automatic updates

The `Sync Letterboxd and publish` workflow runs on pushes to `main`, manually in Actions, and approximately every six hours. It reads `hejrafa` and `annso` public RSS feeds, stores the snapshot, builds static HTML, and deploys to GitHub Pages. GitHub schedules can be delayed; scheduled runs in inactive public repositories may be disabled after 60 days. Re-enable the workflow if necessary.

GitHub Settings → Pages → Source must be **GitHub Actions**. No browser-side feed requests or CORS proxy are needed. The whole page is generated HTML, with small JavaScript enhancements for filtering and showing more reviews. If a feed temporarily fails, its saved content is retained. If no saved data exists for an account, the build fails rather than publishing a misleading empty page.

The overview alternates between the two authors. Filters show each author's reviews in watched-date order. Cards use the first two sentences, with a 180-character cap, and link to the original full review. Original wording is preserved. Spoiler-marked reviews are not quoted. The footer shows each author's four favorite films from `data/favorites.json`, which is edited by hand (favorites rarely change and Letterboxd blocks automated profile requests). Each entry needs a title, year, TMDB id and TMDB poster URL; posters link to `letterboxd.com/tmdb/<id>/`, which redirects to the film page. If a poster is missing or fails to load, the title shows instead. RSS is a rolling recent-activity window, not the entire Letterboxd history; snapshots preserve previously fetched entries. Historical edits/deletions outside that window require updating the saved snapshot manually.

## Rafael's Top 20

`top-20.html` (and `/en/top-20.html`) shows Rafael's yearly Top 20 lists from Letterboxd, one year at a time; without JavaScript every year is listed in full. The homepage shows the latest list's top five above the favorites, and Rafael's review cards get a rank badge (e.g. *#5 · Top 20 2026*) that links to that year. If a film is on more than one list, the most recent one wins. On the page, films Rafael has reviewed link to their review card.

The lists live in `data/top20.json`, imported locally rather than in Actions, because Letterboxd tends to block automated requests from CI and the RSS feed only includes a list's first 10 films:

```sh
python3 scripts/lists.py          # every year since 2015
python3 scripts/lists.py 2026     # only the current list, e.g. after changing it
```

The script reads each `letterboxd.com/hejrafa/list/top-20-movies-<year>/` page, then each new film's page for its TMDB id, poster and backdrop (films already saved are not fetched again). Commit the updated JSON to publish. Lists from 2015–2021 are not marked as ranked on Letterboxd; their order is used as the ranking.

Under each year, the page says how many films Rafael logged that year and how many of them were released that year (e.g. *161 Filme gesehen, 56 davon Neuerscheinungen.*; the current year starts with *Bisher*) (the share image leaves them out). The numbers come from the Breakdown on his Letterboxd year in review (`letterboxd.com/hejrafa/year/<year>/`), which blocks scripts, so they live in `data/watched.json` and are edited by hand. Update the current year's numbers now and then, and once more when the year ends. Letterboxd counts films by original release year, while the lists follow German release dates, so the second number is close rather than exact.

Each year has a **share as image** button that draws a 1080×1920 story image of all 20 posters with their ranks and Rafael’s star ratings in the browser (share sheet on phones, download on desktops). A canvas can only use images whose server allows it, which TMDB does and Letterboxd does not, so the scheduled sync adds a TMDB poster (`tmdbPoster`) to each list film once, using the `TMDB_READ_TOKEN` secret. The page then shows those posters too. Films without one yet appear in the image as a title tile.

## TMDB backdrops

Add your **TMDB API Read Access Token** to repository Settings → Secrets and variables → Actions as `TMDB_READ_TOKEN`, then run the workflow. Do not paste the token into source files. The API resolves films by the TMDB ID in Letterboxd RSS, avoiding ambiguous title searches. Without the token, the site uses public Letterboxd film-page backdrops where available, then the RSS poster as a fallback. Images stay on their original CDNs. The cache avoids repeatedly fetching already resolved images. When a token is added, cached Letterboxd backdrops are automatically upgraded to TMDB where available.

On mouse hover, review cards play one short flipbook sequence using up to four distinct, text-free TMDB backdrops, then restore the cover. Galleries are cached for all published reviews. On mouse devices, extra images preload shortly before a card scrolls into view and are decoded before display, so the first still appears as soon as the mouse enters; failed images are skipped. Leaving, hiding a card, switching tabs, or enabling reduced motion stops playback. Touch, reduced-motion, and data-saving users keep the static cover. Films without additional stills stay static. The review text stays in place throughout.

TMDB documentation: https://developer.themoviedb.org/docs/getting-started and https://developer.themoviedb.org/docs/image-basics. Film images belong to their respective rights holders. Fonts are self-hosted with their SIL Open Font Licenses in `assets/fonts/`.

## Custom domain: daumenkino.fm

The website’s custom domain is **daumenkino.fm**. Hosting uses GitHub Pages with GitHub Actions. All asset links are relative and also support the repository’s default Pages path. The following steps document the domain setup; DNS verification and certificate status are managed in GitHub Pages settings.

1. At your DNS provider, point the apex domain to GitHub Pages using the records in GitHub’s current documentation: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site.
2. Optionally point `www` to `hejrafa.github.io` using a CNAME record.
3. Set `daumenkino.fm` in this repository’s Settings → Pages → Custom domain.
4. Once DNS checks and the certificate finish, enable **Enforce HTTPS**.
5. Verify domain ownership using the TXT record GitHub provides in your account’s Pages settings.

No DNS settings are changed by this repository. For an Actions deployment, configure the custom domain in Pages settings; GitHub does not require a deployed CNAME file.

## Languages

The header links German (`/`) and English (`/en/`) versions. Each is fully rendered HTML with its own title, canonical URL, language, and accessibility labels, so links can be shared and crawled without JavaScript. Language comes from the URL; there are no automatic redirects. Review quotes and film titles retain their original wording. Both pages show all reviews without JavaScript. With JavaScript, author filters and progressive loading reduce page length.

## Content and layout

- `index.html`: German page copy, podcast and Instagram URLs, layout template.
- `styles.css`: responsive visual design, self-hosted typography, reduced-motion behavior.
- `app.js`: author filters, progressive review loading.
- `flipbook.js`: on-demand hover previews with motion and loading safeguards.
- `top20.html`, `top20.js`: the Top 20 page template and its year switcher.
- `share.js`: renders a review card as a 1080×1920 story image in the browser (share sheet on phones, download on desktops).
- CSS and JS links get a content-hash `?v=` at build time, so deploys never mix new HTML with cached old files.
- `scripts/sync.py`: RSS import and image enrichment, server-side only.
- `scripts/build.py`: safely escaped static rendering.
- `scripts/lists.py`: local Top 20 import from Letterboxd list pages.
- `data/letterboxd.json`: committed source snapshot and growing review archive.
- `data/top20.json`: Rafael's yearly Top 20 lists, updated by hand with `scripts/lists.py`.

The footer’s “since 2019” line and podcast structured-data publication date refer to **24 July 2019**, the release date of **#000 Die Namensfindung**, verified against the [official podcast RSS feed](https://anchor.fm/s/cbef5f8/podcast/rss).

Podcast links currently open the existing show/archive. No new short audio episodes are invented or connected to reviews. Per-film audio can be added once those episodes exist.

## Search and accessibility

The build writes reciprocal hreflang links, canonical URLs, robots.txt, sitemap.xml, and JSON-LD describing the website, podcast, authors, films, and actual review excerpts/ratings. Spoiler reviews are excluded from structured review text. Review anchor links reveal their card when opened. No invented ratings, keyword stuffing, or special AI ranking claims.

`SITE_URL` sets the public base URL. The Pages workflow obtains it from `actions/configure-pages` before building, so a future custom domain configuration updates all canonical/discovery URLs. For a local build the default is the current GitHub Pages address. `robots.txt` at a project-path URL cannot control a host's root robots policy; it becomes authoritative once the site is served at the root of the custom domain. Submit the sitemap to Google Search Console and Bing Webmaster Tools after domain verification. Indexing and AI citations are controlled by those services.

Accessibility includes semantic landmarks and review names, a skip link, localized star labels, new-tab descriptions, visible keyboard focus, live filter counts, reduced motion, and focusing the first newly revealed film heading. Decorative stills and symbols do not add screen-reader noise. Automated structure and keyboard checks are not a full assistive-technology or WCAG conformance audit.
