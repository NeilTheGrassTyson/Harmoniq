# BRAND_ASSETS.md

> How the Harmoniq logo is served, and what to do when it needs to leave the app.
> Design rules for the mark live in DESIGN_SYSTEM.md §6.1. The decision behind
> it lives in ADR 0012.

---

## 1. What ships where

| File                                    | Served at                        | Purpose                                  |
| --------------------------------------- | -------------------------------- | ---------------------------------------- |
| `frontend/src/app/icon.svg`             | `/icon.svg`                      | Browser tab icon (all modern browsers)   |
| `frontend/src/app/apple-icon.tsx`       | `/apple-icon`                    | iOS home screen, 180×180 PNG             |
| `frontend/public/brand/harmoniq-mark.svg`      | `/brand/harmoniq-mark.svg`      | Full-colour mark, outside the app  |
| `frontend/public/brand/harmoniq-mark-mono.svg` | `/brand/harmoniq-mark-mono.svg` | One-colour mark                    |

`icon.svg` and `apple-icon.tsx` are **Next.js metadata file conventions**.
Placing them in `src/app/` is the entire wiring — Next injects the `<link>`
tags into every page automatically. There is nothing to add to `layout.tsx`,
and you should not add `<link rel="icon">` by hand; doing so produces duplicate
tags that browsers resolve unpredictably.

Verify after any change:

```bash
cd frontend && npm run build
```

Both routes should appear in the route table as `○ /icon.svg` and
`○ /apple-icon` (`○` = prerendered static).

---

## 2. Required cleanup: delete the old favicon

`frontend/src/app/favicon.ico` predates the logo and still wins the
`/favicon.ico` slot, which several browsers and most link-preview crawlers
request by name regardless of what `<link>` tags say. While it exists, some
surfaces will show the old icon and some the new one.

```bash
git rm frontend/src/app/favicon.ico
```

This is left for you to run deliberately rather than done automatically — it
deletes a committed binary, and it is the one step that changes what existing
users already have cached.

---

## 3. Making it render over HTTPS

Nothing here needs a special server configuration. Both icon routes are static
assets emitted at build time and served by Vercel over HTTPS on the project's
domain, with the correct `content-type` (`image/svg+xml` and `image/png`
respectively — confirmed in the build output's route metadata).

The steps that actually matter in production:

1. **Deploy the branch.** Vercel builds `frontend/` and serves
   `https://<your-domain>/icon.svg` and `https://<your-domain>/apple-icon`.
2. **Confirm the headers**, not just that an image appears:

   ```bash
   curl -sI https://<your-domain>/icon.svg | grep -i content-type
   ```

   Expect `image/svg+xml`. If you get `text/html`, the route did not build and
   you are looking at the app's 404 page rendering in an `<img>`.
3. **Hard-refresh to see it.** Favicons are cached aggressively and per-origin;
   a normal reload will keep showing the old one. Use a private window to check
   what a first-time visitor actually gets.
4. **Mixed content:** the SVG references no external resources — no fonts, no
   images, no CSS. It cannot trigger a mixed-content block. If an icon fails to
   load over HTTPS, the cause is the route or the cache, not the asset.

### Social / link previews

Not yet built. A shared Harmoniq link currently has no `og:image`, so it
previews as a bare title and description. When that matters, the same pattern
as `apple-icon.tsx` applies — an `opengraph-image.tsx` in `src/app/` using
`next/og`. Deliberately out of scope for the logo work.

---

## 4. When the logo has to leave the app

**The wordmark is a React component** (`components/brand/Wordmark.tsx`), not a
file you can hand to someone. The word is live text in Space Grotesk, which
`next/font` loads for the app. Outside the app that font is not guaranteed, so:

- **Do not** ship `Wordmark.tsx`'s markup as an `.svg` with `<text>` in it. On
  a machine without Space Grotesk it silently renders in a fallback face — a
  wrong logo that still looks plausible, which is worse than a broken one.
- **For press, social, a partner's site, or print:** export a PNG at the size
  needed, or have the letterforms converted to outlines once in a vector editor
  and commit the result as `public/brand/harmoniq-wordmark.svg`. This repo has
  no tooling that can outline text — there is no ImageMagick, Inkscape,
  rsvg-convert, Pillow, or cairosvg on the development machine, which is also
  why `apple-icon` is generated at build time instead of committed.

**The square mark has no such constraint** — it is pure geometry.
`harmoniq-mark.svg` and `harmoniq-mark-mono.svg` are safe to send anywhere.

---

## 5. Colour

The mark is `#19d8ff` (`--color-brand`). This is **not** the interface accent
`#2f8cff` (`--color-accent`), and the two are not to be unified without the
WCAG work described in DESIGN_SYSTEM.md §2. On anything that is not a Harmoniq
dark surface, use `harmoniq-mark-mono.svg` rather than placing the neon on an
arbitrary background — it was drawn for near-black and loses a lot of its
contrast on white.
