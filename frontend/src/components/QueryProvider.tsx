"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

/**
 * One QueryClient per browser session, created lazily inside useState so the
 * server render never shares a client between requests (TanStack's App Router
 * guidance). Server Components keep fetching with direct awaits and hand
 * results down as initialData — the client owns only revalidation.
 */
export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // RSC passes fresh initialData on navigation; don't refetch the
            // moment a component mounts on top of it.
            staleTime: 30_000,
            retry: 1,
          },
        },
      })
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
