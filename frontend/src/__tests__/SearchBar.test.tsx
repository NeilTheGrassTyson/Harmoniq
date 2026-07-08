import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import SearchBar from "@/components/SearchBar";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockPush = vi.fn();
let mockPathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    onClick,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} onClick={onClick} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} />
  ),
}));

vi.mock("@/components/AvatarImage", () => ({
  default: ({ username }: { username: string }) => <span data-testid={`avatar-${username}`} />,
}));

const mockSearchCatalog = vi.fn();
const mockSearchUsers = vi.fn();

vi.mock("@/lib/catalog", () => ({
  searchCatalog: (...args: unknown[]) => mockSearchCatalog(...args),
}));

vi.mock("@/lib/users", () => ({
  searchUsers: (...args: unknown[]) => mockSearchUsers(...args),
}));

const emptyMusic = { artists: [], albums: [], tracks: [] };
const sampleUsers = [
  { username: "beatles_fan", display_name: "Beatles Fan", avatar_url: null },
  { username: "stones_lover", display_name: "Stones Lover", avatar_url: null },
];

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SearchBar — People section", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPathname = "/";
    mockPush.mockClear();
    mockSearchCatalog.mockResolvedValue(emptyMusic);
    mockSearchUsers.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders People section when user results are returned", async () => {
    mockSearchUsers.mockResolvedValue(sampleUsers);

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(screen.getByText("People")).toBeTruthy();
    expect(screen.getByText("Beatles Fan")).toBeTruthy();
    expect(screen.getByText("@beatles_fan")).toBeTruthy();
  });

  it("omits People section when user results are empty", async () => {
    mockSearchCatalog.mockResolvedValue({
      artists: [{ mbid: "a1", name: "The Beatles", disambiguation: null, image_url: null }],
      albums: [],
      tracks: [],
    });
    mockSearchUsers.mockResolvedValue([]);

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(screen.queryByText("People")).toBeNull();
    expect(screen.getByText("The Beatles")).toBeTruthy();
  });

  it("shows music results even when user search fails", async () => {
    mockSearchCatalog.mockResolvedValue({
      artists: [{ mbid: "a1", name: "The Beatles", disambiguation: null, image_url: null }],
      albums: [],
      tracks: [],
    });
    mockSearchUsers.mockRejectedValue(new Error("network error"));

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(screen.queryByText("People")).toBeNull();
    expect(screen.getByText("The Beatles")).toBeTruthy();
  });

  it("links each user result to /u/[username]", async () => {
    mockSearchUsers.mockResolvedValue(sampleUsers);

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    const link = screen.getByRole("link", { name: /Beatles Fan/ });
    expect(link.getAttribute("href")).toBe("/u/beatles_fan");
  });
});

describe("SearchBar — URL sync on /search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPush.mockClear();
    mockSearchCatalog.mockResolvedValue(emptyMusic);
    mockSearchUsers.mockResolvedValue(sampleUsers);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("pushes ?q= URL when typing on /search", async () => {
    mockPathname = "/search";

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(mockPush).toHaveBeenCalledWith("/search?q=beatles");
  });

  it("does NOT push URL when typing on pages other than /search", async () => {
    mockPathname = "/";

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  it("does NOT push URL when typing on an artist page", async () => {
    mockPathname = "/artist/some-mbid";

    render(<SearchBar />);
    const input = screen.getByRole("searchbox");

    fireEvent.change(input, { target: { value: "beatles" } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(mockPush).not.toHaveBeenCalled();
  });
});
