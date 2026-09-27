import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WebsiteAppearance from "@/components/WebsiteAppearance";

const mockSetAppearance = vi.fn();
vi.mock("@/app/settings/actions", () => ({
  setAppearance: (...args: unknown[]) => mockSetAppearance(...args),
}));

const html = document.documentElement;

describe("WebsiteAppearance", () => {
  beforeEach(() => {
    mockSetAppearance.mockReset();
    html.removeAttribute("data-theme");
  });

  it("is headed 'Website Appearance' and offers exactly three themes", () => {
    render(<WebsiteAppearance initial="midnight" />);
    expect(screen.getByText("Website Appearance")).toBeTruthy();
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => (r as HTMLInputElement).value)).toEqual(["light", "dark", "midnight"]);
    expect((screen.getByRole("radio", { name: "Midnight" }) as HTMLInputElement).checked).toBe(
      true
    );
  });

  it("repaints the page immediately and saves the choice", async () => {
    mockSetAppearance.mockResolvedValue({ ok: true });
    render(<WebsiteAppearance initial="midnight" />);

    fireEvent.click(screen.getByRole("radio", { name: "Light" }));

    expect(html.getAttribute("data-theme")).toBe("light");
    await waitFor(() => expect(mockSetAppearance).toHaveBeenCalledWith("light"));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("removes the attribute for Midnight, the base theme", async () => {
    mockSetAppearance.mockResolvedValue({ ok: true });
    html.setAttribute("data-theme", "dark");
    render(<WebsiteAppearance initial="dark" />);

    fireEvent.click(screen.getByRole("radio", { name: "Midnight" }));

    expect(html.hasAttribute("data-theme")).toBe(false);
    await waitFor(() => expect(mockSetAppearance).toHaveBeenCalledWith("midnight"));
  });

  it("puts the previous theme back and says so when the save fails", async () => {
    mockSetAppearance.mockRejectedValue(new Error("network"));
    html.setAttribute("data-theme", "dark");
    render(<WebsiteAppearance initial="dark" />);

    fireEvent.click(screen.getByRole("radio", { name: "Light" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/couldn't save/i));
    expect(html.getAttribute("data-theme")).toBe("dark");
    expect((screen.getByRole("radio", { name: "Dark" }) as HTMLInputElement).checked).toBe(true);
  });

  it("treats a refused value the same as a failed save", async () => {
    mockSetAppearance.mockResolvedValue({ ok: false });
    render(<WebsiteAppearance initial="midnight" />);

    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(html.hasAttribute("data-theme")).toBe(false);
  });
});
