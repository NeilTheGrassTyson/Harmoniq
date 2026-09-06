import type { MetadataRoute } from "next";

// Web app manifest — another Next metadata file convention, served at
// /manifest.webmanifest with the <link rel="manifest"> injected automatically.
// Do not add that tag by hand.
//
// Icons point at the committed rasters rather than at icon.svg: installed-app
// surfaces (Android home screen, Chrome's install prompt) want PNG at known
// pixel sizes, and these two are already the render masters — see
// docs/BRAND_ASSETS.md §1.

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Harmoniq",
    short_name: "Harmoniq",
    description: "A social music discovery network built around trust and musical identity.",
    start_url: "/",
    display: "standalone",
    // The canvas and brand token values. A manifest is read by the OS before
    // any stylesheet exists, so these are necessarily literals.
    background_color: "#0b0d12",
    theme_color: "#0b0d12",
    icons: [
      {
        src: "/brand/harmoniq-mark-512.png",
        sizes: "512x512",
        type: "image/png",
        // "any", not "maskable": these rasters carry the mark's own rounded
        // rect out to the edge, so a maskable crop would clip the wave.
        purpose: "any",
      },
      {
        src: "/brand/harmoniq-mark-1024.png",
        sizes: "1024x1024",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
