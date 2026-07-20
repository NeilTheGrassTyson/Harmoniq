import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/** Fresh client per test so no cache bleeds between cases. */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

/** Wrapper for renderHook and custom render trees. */
export function queryWrapper() {
  const client = createTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/** Drop-in replacement for render() for components that use TanStack Query. */
export function renderWithQuery(ui: React.ReactElement) {
  const Wrapper = queryWrapper();
  return render(<Wrapper>{ui}</Wrapper>);
}
