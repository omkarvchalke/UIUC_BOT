import { useEffect, useMemo, useState } from "react";
import { getSources } from "../services/api";
import SourceCard from "../components/SourceCard";
import DisclaimerBanner from "../components/DisclaimerBanner";
import type { SourceItem } from "../types";

export default function Sources() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSources()
      .then((data) => setSources(data.sources))
      .catch(() =>
        setError(
          "Sorry, something went wrong reaching the backend. Please make sure the API server is running.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(
    () => Array.from(new Set(sources.map((s) => s.category))).sort(),
    [sources],
  );

  const visibleSources = activeCategory
    ? sources.filter((s) => s.category === activeCategory)
    : sources;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Source Library</h1>
        <p className="mt-1 text-sm text-slate-600">
          Every answer CampusGuide AI gives is grounded in one of these public
          university webpages.
        </p>
      </div>

      <DisclaimerBanner />

      <p className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        All sources listed below are official, publicly accessible University
        of Illinois Urbana-Champaign webpages — no login-protected pages,
        student portals, or private systems are ever accessed. Listing a page
        here does not imply that its owning office endorses or is affiliated
        with CampusGuide AI.
      </p>

      {loading && <p className="text-sm text-slate-500">Loading sources…</p>}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveCategory(null)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                activeCategory === null
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-slate-300 text-slate-600 hover:border-brand-500"
              }`}
            >
              All
            </button>
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => setActiveCategory(category)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  activeCategory === category
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-slate-300 text-slate-600 hover:border-brand-500"
                }`}
              >
                {category}
              </button>
            ))}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visibleSources.map((source) => (
              <SourceCard key={source.url} source={source} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
