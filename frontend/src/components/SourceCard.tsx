import type { SourceRef } from "../types";

function formatSourceType(sourceType: string): string {
  return sourceType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function SourceCard({ source }: { source: SourceRef }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm transition hover:border-brand-500 hover:shadow-md"
    >
      <p className="font-medium text-brand-700">{source.title}</p>
      <p className="mt-1 text-xs text-slate-500">
        {source.department} · {source.category}
      </p>
      <p className="mt-1 truncate text-xs text-slate-400">{source.url}</p>
      {source.source_type && (
        <span className="mt-2 inline-block rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-500">
          {formatSourceType(source.source_type)}
        </span>
      )}
    </a>
  );
}
