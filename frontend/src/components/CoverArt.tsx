"use client";

import Image from "next/image";
import { useState } from "react";

interface CoverArtProps {
  src: string | null;
  alt: string;
  /** Fixed-size mode: width and height in px. Required when fill is false (default). */
  size?: number;
  className?: string;
  /**
   * Fill mode: renders via Next.js <Image fill> so the image fills a parent
   * container that is already `position: relative` and has explicit dimensions.
   * When the image is absent or fails to load, renders nothing — the parent's
   * own background and any sibling content (e.g. a placeholder glyph) show through.
   */
  fill?: boolean;
}

export default function CoverArt({
  src,
  alt,
  size = 48,
  className = "",
  fill = false,
}: CoverArtProps) {
  const [failed, setFailed] = useState(false);

  if (fill) {
    if (!src || failed) return null;
    return (
      <div className={`absolute inset-0 overflow-hidden ${className}`}>
        <Image
          src={src}
          alt={alt}
          fill
          sizes="(min-width: 640px) 200px, 130px"
          className="object-cover"
          onError={() => setFailed(true)}
          unoptimized
        />
      </div>
    );
  }

  if (!src || failed) {
    return (
      <div
        className={`bg-tile shrink-0 rounded ${className}`}
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
