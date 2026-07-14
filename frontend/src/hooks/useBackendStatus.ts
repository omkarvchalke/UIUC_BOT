"use client";

import { useEffect, useState } from "react";

import { fetchHealth } from "@/services/api";
import type { HealthResponse } from "@/types/api";

type BackendStatus =
  | { state: "loading" }
  | { state: "online"; health: HealthResponse }
  | { state: "offline" };

export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetchHealth()
      .then((health) => {
        if (!cancelled) setStatus({ state: "online", health });
      })
      .catch(() => {
        if (!cancelled) setStatus({ state: "offline" });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}
