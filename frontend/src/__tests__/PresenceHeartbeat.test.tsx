import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token", isSignedIn: true }),
}));
const mockBeat = vi.fn();
vi.mock("@/lib/presence", () => ({ sendHeartbeat: (...a: unknown[]) => mockBeat(...a) }));

import PresenceHeartbeat from "@/components/PresenceHeartbeat";

let visibility: DocumentVisibilityState = "visible";
Object.defineProperty(document, "visibilityState", { get: () => visibility, configurable: true });

const flush = () => vi.advanceTimersByTimeAsync(0);

describe("PresenceHeartbeat", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockBeat.mockReset();
    visibility = "visible";
  });
  afterEach(() => vi.useRealTimers());

  it("beats on mount and once a minute while visible", async () => {
    mockBeat.mockResolvedValue(true);
    render(<PresenceHeartbeat />);
    await flush();
    expect(mockBeat).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(mockBeat).toHaveBeenCalledTimes(2);
  });

  it("sends nothing while the tab is hidden", async () => {
    mockBeat.mockResolvedValue(true);
    visibility = "hidden";
    render(<PresenceHeartbeat />);
    await vi.advanceTimersByTimeAsync(180_000);
    expect(mockBeat).not.toHaveBeenCalled();
  });

  // Online status Private: the server keeps nothing and says so; the page
  // then stops asking rather than sending beats that go nowhere.
  it("stops for good once the server says it isn't recording", async () => {
    mockBeat.mockResolvedValue(false);
    render(<PresenceHeartbeat />);
    await flush();
    await vi.advanceTimersByTimeAsync(300_000);
    document.dispatchEvent(new Event("visibilitychange"));
    await flush();
    expect(mockBeat).toHaveBeenCalledTimes(1);
  });
});
