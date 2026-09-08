"use client";

import { useQuery } from "@tanstack/react-query";
import { getStreamingLinks } from "@/lib/streaming";
import { errorStatus } from "@/lib/apiBase";

export default function StreamingAccess({ mbid }: { mbid: string }) {
  const query = useQuery({
    queryKey: ["streaming", mbid],
    queryFn: async () => {
      try {
        return await getStreamingLinks(mbid);
      } catch (error) {
        if (errorStatus(error) === 404) return null;
        throw error;
      }
    },
    staleTime: 300_000,
    retry: false,
  });
  if (query.isSuccess && (!query.data || !Array.isArray(query.data.links))) return null;
  return (
    <section aria-label="Listen on" className="mb-8">
      <h2 className="font-display text-tertiary mb-3 text-xs font-medium tracking-wide uppercase">
        Listen on
      </h2>
      {query.isPending ? (
        <p className="text-tertiary text-sm" role="status">
          Finding music services…
        </p>
      ) : query.isError ? (
        <p className="text-tertiary text-sm">
          Couldn&apos;t load music services.{" "}
          <button onClick={() => void query.refetch()} className="underline underline-offset-2">
            Try again
          </button>
        </p>
      ) : (
        <>
          <ul className="flex flex-wrap gap-2">
            {query.data.links.map((link) => (
              <li key={link.provider}>
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  referrerPolicy="no-referrer"
                  className="rounded-control border-hairline text-secondary hover:text-primary inline-block border px-3 py-2 text-sm"
                >
                  {link.kind === "exact" ? "Open in" : "Search"} {link.name}
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              </li>
            ))}
          </ul>
          <p className="text-tertiary mt-2 text-xs">
            {query.data.mapping_status === "unavailable"
              ? "Exact links are temporarily unavailable. "
              : ""}
            Search options help you choose the right version. Save to your library or a playlist in
            your music service.
          </p>
        </>
      )}
    </section>
  );
}
