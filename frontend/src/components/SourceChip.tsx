import type { SourceRef } from "../types";

/**
 * Compact inline citation for the chat view — shows the source *name* only,
 * not the raw URL as visible text (the URL is still the real href/title
 * attribute, so it's one click away, just not printed on screen every
 * time). For the full card with URL/category/department/type visible, see
 * SourceCard.tsx (used on the Sources Library page, where seeing the URL
 * itself is the point).
 */
export default function SourceChip({ source }: { source: SourceRef }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      title={source.url}
      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 transition hover:border-brand-500 hover:bg-brand-50 hover:text-brand-700"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-3 w-3 flex-shrink-0"
      >
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
      </svg>
      {source.title}
    </a>
  );
}
