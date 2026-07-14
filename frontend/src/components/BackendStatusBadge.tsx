"use client";

import { useBackendStatus } from "@/hooks/useBackendStatus";

export function BackendStatusBadge() {
  const status = useBackendStatus();

  const label =
    status.state === "loading"
      ? "Checking backend…"
      : status.state === "online"
        ? `Backend online (${status.health.environment})`
        : "Backend offline";

  const dotColor =
    status.state === "online"
      ? "bg-emerald-500"
      : status.state === "offline"
        ? "bg-red-500"
        : "bg-amber-400";

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-black/10 px-3 py-1 text-sm dark:border-white/10">
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </div>
  );
}
