import { useState } from "react";
import { generateChecklist } from "../services/api";
import type {
  ChecklistRequest,
  ChecklistResponse,
  Housing,
  StudentStatus,
  StudentType,
  Term,
} from "../types";

const DEFAULT_REQUEST: ChecklistRequest = {
  student_type: "freshman",
  student_status: "domestic",
  term: "fall",
  housing: "on-campus",
};

export default function Checklist() {
  const [form, setForm] = useState<ChecklistRequest>(DEFAULT_REQUEST);
  const [result, setResult] = useState<ChecklistResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await generateChecklist(form);
      setResult(response);
    } catch {
      setError(
        "Sorry, something went wrong reaching the backend. Please make sure the API server is running and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Checklist Generator</h1>
        <p className="mt-1 text-sm text-slate-600">
          Build a general new-student onboarding checklist. No name, UIN, NetID,
          password, or visa document details are ever requested.
        </p>
      </div>

      <div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Student type</span>
          <select
            value={form.student_type}
            onChange={(e) =>
              setForm({ ...form, student_type: e.target.value as StudentType })
            }
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="freshman">Freshman</option>
            <option value="transfer">Transfer</option>
            <option value="graduate">Graduate</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Student status</span>
          <select
            value={form.student_status}
            onChange={(e) =>
              setForm({
                ...form,
                student_status: e.target.value as StudentStatus,
              })
            }
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="domestic">Domestic</option>
            <option value="international">International</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Term</span>
          <select
            value={form.term}
            onChange={(e) => setForm({ ...form, term: e.target.value as Term })}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="fall">Fall</option>
            <option value="spring">Spring</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Housing</span>
          <select
            value={form.housing}
            onChange={(e) =>
              setForm({ ...form, housing: e.target.value as Housing })
            }
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="on-campus">On-campus</option>
            <option value="off-campus">Off-campus</option>
            <option value="not sure">Not sure</option>
          </select>
        </label>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={loading}
          className="col-span-full w-fit rounded-full bg-brand-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {loading ? "Generating…" : "Generate Checklist"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {result.disclaimer}
          </p>

          {result.sections.map((section) => (
            <div
              key={section.title}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <h2 className="font-semibold text-slate-900">{section.title}</h2>
              <ul className="mt-2 space-y-2">
                {section.items.map((item, idx) => (
                  <li key={idx} className="text-sm text-slate-700">
                    <span>{item.task}</span>
                    {item.source_url && (
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-xs text-brand-600 hover:underline"
                      >
                        {item.source_title ?? "Source"}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
