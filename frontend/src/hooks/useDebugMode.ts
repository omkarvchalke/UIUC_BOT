"use client";

import { useCallback, useEffect, useState } from "react";

const DEBUG_MODE_KEY = "illiniassist.debugMode";

function readStoredDebugMode(): boolean {
  try {
    return localStorage.getItem(DEBUG_MODE_KEY) === "true";
  } catch {
    return false;
  }
}

interface UseDebugModeResult {
  debugMode: boolean;
  toggleDebugMode: () => void;
}

export function useDebugMode(): UseDebugModeResult {
  const [debugMode, setDebugMode] = useState(false);

  // Same hydration-safe effect-based localStorage sync pattern as
  // useSession/useChat -- SSR has no access to localStorage, so this can't
  // be a lazy useState initializer without mismatching the server-rendered
  // HTML on first client render.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setDebugMode(readStoredDebugMode());
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const toggleDebugMode = useCallback(() => {
    setDebugMode((prev) => {
      const next = !prev;
      localStorage.setItem(DEBUG_MODE_KEY, String(next));
      return next;
    });
  }, []);

  return { debugMode, toggleDebugMode };
}
