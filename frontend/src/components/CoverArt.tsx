"use client";

import Image from "next/image";
import { useState } from "react";

interface CoverArtProps {
  src: string | null;
  alt: string;
  size?: number;
  className?: string;
}

export default function CoverArt({
  src,
  alt,
  size = 48,
  className = "",
}: CoverArtProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        className={`shrink-0 rounded bg-neutral-100 dark:bg-neutral-800 ${className}`}
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
    );
  }

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded ${className}`}
      style={{ width: size, height: size }}
    >
      <Image
        src={src}
        alt={alt}
        fill
        sizes={`${size}px`}
        className="object-cover"
        onError={() => setFailed(true)}
        unoptimized
      />
    </div>
  );
}
