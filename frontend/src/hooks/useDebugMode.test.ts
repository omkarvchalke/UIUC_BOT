import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useDebugMode } from "./useDebugMode";

describe("useDebugMode", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("starts false when nothing is stored", async () => {
    const { result } = renderHook(() => useDebugMode());

    await waitFor(() => expect(result.current.debugMode).toBe(false));
  });

  it("toggling flips state and persists to localStorage", async () => {
    const { result } = renderHook(() => useDebugMode());
    await waitFor(() => expect(result.current.debugMode).toBe(false));

    act(() => {
      result.current.toggleDebugMode();
    });

    expect(result.current.debugMode).toBe(true);
    expect(localStorage.getItem("illiniassist.debugMode")).toBe("true");

    act(() => {
      result.current.toggleDebugMode();
    });

    expect(result.current.debugMode).toBe(false);
    expect(localStorage.getItem("illiniassist.debugMode")).toBe("false");
  });

  it("restores a previously persisted true value on a fresh render", async () => {
    localStorage.setItem("illiniassist.debugMode", "true");

    const { result } = renderHook(() => useDebugMode());

    await waitFor(() => expect(result.current.debugMode).toBe(true));
  });
});
