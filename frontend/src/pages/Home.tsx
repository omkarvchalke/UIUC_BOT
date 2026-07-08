import { Link } from "react-router-dom";
import DisclaimerBanner from "../components/DisclaimerBanner";
import PrivacyBanner from "../components/PrivacyBanner";

const FEATURES = [
  {
    title: "Ask questions",
    description:
      "Ask general new-student questions about orientation, housing, i-cards, and more.",
    to: "/chat",
  },
  {
    title: "Get source-cited answers",
    description:
      "Every answer links back to the official public webpage it was drawn from.",
    to: "/sources",
  },
  {
    title: "Generate a general checklist",
    description:
      "Build a general onboarding checklist based on your student type and status.",
    to: "/checklist",
  },
  {
    title: "Find the right office/resource",
    description:
      "Browse the full library of curated public sources by category.",
    to: "/sources",
  },
];

export default function Home() {
  return (
    <div className="space-y-8">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold text-slate-900">CampusGuide AI</h1>
        <p className="text-lg text-slate-600">
          Unofficial RAG assistant for public UIUC new-student information
        </p>
      </div>

      <DisclaimerBanner />
      <PrivacyBanner />

      <div className="grid gap-4 sm:grid-cols-2">
        {FEATURES.map((feature) => (
          <Link
            key={feature.title}
            to={feature.to}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-brand-500 hover:shadow-md"
          >
            <h2 className="font-semibold text-brand-700">{feature.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{feature.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
