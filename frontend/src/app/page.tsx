import { BackendStatusBadge } from "@/components/BackendStatusBadge";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 px-6 text-center dark:bg-black">
      <h1 className="text-4xl font-semibold tracking-tight text-black dark:text-zinc-50">
        IlliniGuide AI
      </h1>
      <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
        An AI-powered onboarding assistant for UIUC students. Chat UI arrives
        in a later phase — this page currently verifies the frontend↔backend
        wiring.
      </p>
      <BackendStatusBadge />
    </div>
  );
}
