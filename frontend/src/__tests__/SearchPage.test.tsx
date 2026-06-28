import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SearchPage from "@/app/search/page";

// ── Module mocks ──────────────────────────────────────────────────────────────

let mockQ: string | null = null;

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (key: string) => (key === "q" ? mockQ : null) }),
  usePathname: () => "/search",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

vi.mock("@/components/AppShell", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/AvatarImage", () => ({
  default: ({ username }: { username: string }) => (
    <span data-testid={`avatar-${username}`} />
  ),
}));

vi.mock("@/components/EqualizerGlyph", () => ({
  default: () => <svg data-testid="equalizer-glyph" />,
}));

const mockSearchCatalog = vi.fn();
const mockSearchUsers = vi.fn();

vi.mock("@/lib/catalog", () => ({
  searchCatalog: (...args: unknown[]) => mockSearchCatalog(...args),
}));

vi.mock("@/lib/users", () => ({
  searchUsers: (...args: unknown[]) => mockSearchUsers(...args),
}));

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SearchPage", () => {
  beforeEach(() => {
    mockQ = null;
    mockSearchCatalog.mockResolvedValue({ artists: [], albums: [], tracks: [] });
    mockSearchUsers.mockResolvedValue([]);
  });

  it("shows empty state with EqualizerGlyph when no q param", () => {
    mockQ = null;
    render(<SearchPage />);

    expect(screen.getByTestId("equalizer-glyph")).toBeTruthy();
    expect(screen.getByText("Search for music or people")).toBeTruthy();
  });

  it("shows empty state when q is too short", () => {
    mockQ = "a";
    render(<SearchPage />);

    expect(screen.getByTestId("equalizer-glyph")).toBeTruthy();
    expect(screen.getByText("Search for music or people")).toBeTruthy();
  });

  it("renders People results when q >= 2 chars and users are returned", async () => {
    mockQ = "beatles";
    mockSearchUsers.mockResolvedValue([
      { username: "beatles_fan", display_name: "Beatles Fan", avatar_url: null },
    ]);

    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("People")).toBeTruthy();
      expect(screen.getByText("Beatles Fan")).toBeTruthy();
      expect(screen.getByText("@beatles_fan")).toBeTruthy();
    });
  });

  it("renders Music results when q >= 2 chars and catalog results are returned", async () => {
    mockQ = "beatles";
    mockSearchCatalog.mockResolvedValue({
      artists: [
        { mbid: "a1", name: "The Beatles", disambiguation: null, image_url: null },
      ],
      albums: [],
      tracks: [],
    });

    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("Artists")).toBeTruthy();
      expect(screen.getByText("The Beatles")).toBeTruthy();
    });
  });

  it("People section link navigates to /u/[username]", async () => {
    mockQ = "beatles";
    mockSearchUsers.mockResolvedValue([
      { username: "beatles_fan", display_name: "Beatles Fan", avatar_url: null },
    ]);

    render(<SearchPage />);

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /Beatles Fan/ });
      expect(link.getAttribute("href")).toBe("/u/beatles_fan");
    });
  });

  it("does not render People section when user results are empty", async () => {
    mockQ = "beatles";
    mockSearchCatalog.mockResolvedValue({
      artists: [
        { mbid: "a1", name: "The Beatles", disambiguation: null, image_url: null },
      ],
      albums: [],
      tracks: [],
    });
    mockSearchUsers.mockResolvedValue([]);

    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.queryByText("People")).toBeNull();
      expect(screen.getByText("Artists")).toBeTruthy();
    });
  });
});
