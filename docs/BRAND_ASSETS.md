# BRAND_ASSETS.md

> How the Harmoniq logo is served, and what to do when it needs to leave the app.
> Design rules for the mark live in DESIGN_SYSTEM.md §6.1. The decision behind
> it lives in ADR 0013.

---

## 1. What ships where

| File                                    | Served at                        | Purpose                                  |
| --------------------------------------- | -------------------------------- | ---------------------------------------- |
| `frontend/src/app/icon.svg`             | `/icon.svg`                      | Browser tab icon (all modern browsers)   |
| `frontend/src/app/apple-icon.tsx`       | `/apple-icon`                    | iOS home screen, 180×180 PNG             |
| `frontend/src/app/favicon.ico`           | `/favicon.ico`                   | Legacy favicon slot, 16/32/48            |
| `frontend/public/brand/harmoniq-mark.svg`      | `/brand/harmoniq-mark.svg`      | Full-colour mark, outside the app  |
| `frontend/public/brand/harmoniq-mark-mono.svg` | `/brand/harmoniq-mark-mono.svg` | One-colour mark                    |
| `frontend/public/brand/harmoniq-mark-512.png`  | `/brand/harmoniq-mark-512.png`  | Raster master, transparent corners |
| `frontend/public/brand/harmoniq-mark-1024.png` | `/brand/harmoniq-mark-1024.png` | Raster master, store/press sizes   |
| `frontend/public/brand/harmoniq-wordmark.png`     | `/brand/harmoniq-wordmark.png`     | Full lockup, light text for dark surfaces |
| `frontend/public/brand/harmoniq-wordmark-ink.png` | `/brand/harmoniq-wordmark-ink.png` | Full lockup, ink for light surfaces |
| `frontend/public/brand/fonts/SpaceGrotesk-Medium.ttf` | *(not served as a font)* | Render input only — see §2 |

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

## 2. Rasters, and how they were made

There is no rasteriser on the development machine — no ImageMagick, Inkscape,
rsvg-convert, Pillow, or cairosvg. Every raster here was therefore rendered by
**Next itself**, via a temporary `generateImageMetadata` export on
`apple-icon.tsx` that emitted the mark at 16/32/48/180/512/1024, followed by a
build. The wordmark rasters came the same way, passing the bundled TTF through
`ImageResponse`'s `fonts` option and cropping the result to its ink. The PNG bodies were lifted out of `.next/server/app/apple-icon/`, the
`.ico` was assembled from the 16/32/48 payloads, and the temporary export was
reverted.

To redo it (after a mark change), repeat that: add `generateImageMetadata`
listing the sizes, `npm run build`, take the `.body` files, revert. Note that
in this version of Next the `id` prop is a **Promise** and must be awaited —
`Number(id)` without `await` yields `NaN` and the build fails inside satori
with `inputValue.trim is not a function`, which does not point anywhere near
the real cause.

`favicon.ico` is a Vista-era ICO carrying **PNG** payloads rather than BMP.
Every modern browser and Windows Explorer reads this; software older than
roughly 2007 does not.

The small sizes are a **redraw, not a scale**: at 16–48px the overtone falls
under a pixel and reads as noise, so those renders drop it and thicken the
fundamental, matching `icon.svg` and `OctaveMark`'s `compact` prop.

The old pre-logo `favicon.ico` has been replaced in place, so there is no
longer a cleanup step here and no icon slot still serving the previous mark.

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

**Rasters exist for both marks**, so most requests are already answered:

- Square mark — `harmoniq-mark-512.png` / `-1024.png`, or the SVGs where
  vector is accepted.
- Wordmark — `harmoniq-wordmark.png` (light text, for dark surfaces) and
  `harmoniq-wordmark-ink.png` (dark text, for light ones). Both 1351×402,
  transparent, cropped to the ink with a 20px margin.

**There is still no outlined wordmark SVG.** `Wordmark.tsx` renders live Space
Grotesk, and nothing here can convert letterforms to paths. Do **not** work
around that by shipping an `.svg` with `<text>` in it: on a machine without
the font it silently renders in a fallback face — a wrong logo that still
looks plausible, which is worse than a broken one. If a vector wordmark is
ever needed, outline it once in a vector editor and commit the result as
`public/brand/harmoniq-wordmark.svg`.

### The bundled font

`public/brand/fonts/SpaceGrotesk-Medium.ttf` (static, OS/2 weight 500) exists
so the wordmark rasters are reproducible. It is a **build input, not a served
webfont** — the app still loads Space Grotesk through `next/font` in
`layout.tsx`, and nothing should `@font-face` this file.

It is redistributed under the SIL Open Font License 1.1; `OFL.txt` sits beside
it and must stay there. Two OFL terms worth knowing before anyone touches it:
the font may not be sold on its own, and any **modified** version must not use
the reserved name "Space Grotesk."

Getting it was less obvious than expected, so: the google/fonts repo ships
**only** the variable `SpaceGrotesk[wght].ttf`, whose default instance is
Light 300 — the wrong weight, and satori will not instance it. There is no
`static/` directory (that path 404s to an HTML page). The static Medium comes
from the Google Fonts CSS API queried with a **plain `Mozilla/5.0`**
user-agent, which returns a `.ttf` URL; a legacy MSIE user-agent returns EOT
instead, whose first four bytes are the file length rather than a font magic.

## 5. Colour

The mark is `#19d8ff` (`--color-brand`). This is **not** the interface accent
`#2f8cff` (`--color-accent`), and the two are not to be unified without the
WCAG work described in DESIGN_SYSTEM.md §2. On anything that is not a Harmoniq
dark surface, use `harmoniq-mark-mono.svg` rather than placing the neon on an
arbitrary background — it was drawn for near-black and loses a lot of its
contrast on white.
