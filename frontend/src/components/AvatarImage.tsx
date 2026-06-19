"use client";

import Image from "next/image";
import { useState } from "react";

interface AvatarImageProps {
  src: string | null | undefined;
  username: string;
  size: number;
  className?: string;
}

// Deterministic hue from a string — gives each user a consistent placeholder colour.
function _hue(username: string): number {
  let h = 0;
  for (let i = 0; i < username.length; i++) {
    h = (h * 31 + username.charCodeAt(i)) & 0xffffff;
  }
  return h % 360;
}

function _initials(username: string): string {
  return username.slice(0, 2).toUpperCase();
}

/**
 * Avatar image with an initials-based placeholder.
 * Falls back to the placeholder on load error or when src is absent.
 * Never shows a broken image icon.
 */
export default function AvatarImage({
  src,
  username,
  size,
  className = "",
}: AvatarImageProps) {
  const [failed, setFailed] = useState(false);

  const hue = _hue(username);
  const bg = `hsl(${hue} 35% 55%)`;
  const roundedClass = className || "rounded-full";

  if (!src || failed) {
    return (
      <div
        className={`flex shrink-0 items-center justify-center font-light text-white ${roundedClass}`}
        style={{
          width: size,
          height: size,
          background: bg,
          fontSize: Math.max(10, Math.round(size * 0.35)),
        }}
        aria-label={username}
      >
        {_initials(username)}
      </div>
    );
  }

  return (
    <div
      className={`relative shrink-0 overflow-hidden ${roundedClass}`}
      style={{ width: size, height: size }}
    >
      <Image
        src={src}
        alt={username}
        fill
        sizes={`${size}px`}
        unoptimized
        onError={() => setFailed(true)}
        className="object-cover"
      />
    </div>
  );
}
