import type { NextConfig } from "next";

// Set when sharing the dev server over Tailscale so someone else can try a
// branch — the bare MagicDNS name, no scheme and no port, e.g.
// "yourmachine.tailnet-name.ts.net". See docs/DEV_SHARING.md.
//
// Next blocks cross-origin requests to dev-only assets and endpoints unless
// the origin is listed here, so without it the page loads and then HMR and
// the /_next/* dev assets fail — which looks like a broken build rather than
// a blocked origin. Read from the environment rather than committed: the
// hostname is specific to one machine and one tailnet, and hardcoding it
// would both leak it and only ever work for one person.
const tailnetHost = process.env.HARMONIQ_DEV_TAILNET_HOST?.trim();

const nextConfig: NextConfig = {
  // Absent unless the variable is set, so normal local dev is untouched.
  ...(tailnetHost ? { allowedDevOrigins: [tailnetHost] } : {}),
  images: {
    // Cover Art Archive — album artwork
    remotePatterns: [
      {
        protocol: "https",
        hostname: "coverartarchive.org",
      },
      {
        protocol: "https",
        hostname: "*.coverartarchive.org",
      },
    ],
  },
};

export default nextConfig;
