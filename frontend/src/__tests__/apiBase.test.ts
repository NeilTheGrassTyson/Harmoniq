import { describe, it, expect } from "vitest";
import { errorStatus, isNetworkError, isUpstreamFailure, friendlyError } from "@/lib/apiBase";

const httpError = (status: number, message = "boom") =>
  Object.assign(new Error(message), { status });

describe("errorStatus", () => {
  it("reads the status attached by the API helpers", () => {
    expect(errorStatus(httpError(404))).toBe(404);
  });

  it("is undefined when the request never got a response", () => {
    expect(errorStatus(new TypeError("Load failed"))).toBeUndefined();
    expect(errorStatus("not an error")).toBeUndefined();
  });

  it("ignores a non-numeric status", () => {
    expect(errorStatus({ status: "500" })).toBeUndefined();
  });
});

describe("isNetworkError", () => {
  it("is true only when no status came back", () => {
    expect(isNetworkError(new TypeError("Load failed"))).toBe(true);
    expect(isNetworkError(httpError(409))).toBe(false);
  });
});

describe("isUpstreamFailure", () => {
  it("covers a request that never reached the backend", () => {
    expect(isUpstreamFailure(new TypeError("Load failed"))).toBe(true);
  });

  it("covers 5xx", () => {
    expect(isUpstreamFailure(httpError(500))).toBe(true);
    expect(isUpstreamFailure(httpError(503))).toBe(true);
  });

  it("excludes client errors, which are not outages", () => {
    expect(isUpstreamFailure(httpError(404))).toBe(false);
    expect(isUpstreamFailure(httpError(403))).toBe(false);
    expect(isUpstreamFailure(httpError(409))).toBe(false);
  });
});

describe("friendlyError", () => {
  it("never surfaces a raw fetch rejection", () => {
    const message = friendlyError(new TypeError("Load failed"));
    expect(message).toBe("Couldn't reach Harmoniq. Check your connection and try again.");
    expect(message).not.toContain("Load failed");
  });

  it("passes through a server message written for users", () => {
    expect(friendlyError(httpError(409, "That username is taken."))).toBe(
      "That username is taken."
    );
  });

  it("uses the caller's fallback when the server gave no message", () => {
    expect(friendlyError(Object.assign(new Error(""), { status: 500 }), "Couldn't delete.")).toBe(
      "Couldn't delete."
    );
  });
});
