import DisclaimerBanner from "../components/DisclaimerBanner";

export default function About() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">About CampusGuide AI</h1>

      <DisclaimerBanner />

      <section className="space-y-2">
        <h2 className="font-semibold text-slate-900">What this is</h2>
        <p className="text-sm text-slate-700">
          CampusGuide AI is a student-built portfolio project that uses
          Retrieval-Augmented Generation (RAG) over a curated set of{" "}
          <strong>public</strong> UIUC webpages to answer general new-student
          questions — orientation, Welcome Week, housing, move-in, i-cards,
          NetID basics, international student check-in, transportation, health
          resources, and accessibility accommodations. Every answer includes
          citations back to the public source it was drawn from.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold text-slate-900">What this is not</h2>
        <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
          <li>Not an official University of Illinois Urbana-Champaign service.</li>
          <li>Not connected to Canvas, Banner, student portals, or email.</li>
          <li>Not a source of immigration, legal, medical, or financial advice.</li>
          <li>Not able to check admission status, grades, or account details.</li>
          <li>Not able to make official decisions on your behalf.</li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold text-slate-900">
          Privacy and safety boundaries
        </h2>
        <p className="text-sm text-slate-700">
          CampusGuide AI never requests, collects, stores, or processes UIN,
          NetID passwords, passport numbers, SEVIS IDs, I-20 details, visa
          document numbers, health or immunization records, financial aid or
          tuition details, grades, class schedules, admission records, housing
          contract details, or any other private student record. Sensitive or
          student-specific questions receive a safe fallback response directing
          you to the relevant official office.
        </p>
      </section>
    </div>
  );
}
