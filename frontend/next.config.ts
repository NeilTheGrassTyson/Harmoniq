import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
