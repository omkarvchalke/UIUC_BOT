"use client";

import { useCallback, useEffect, useState } from "react";

import { createSession } from "@/services/chatApi";
import type { StudentType } from "@/types/chat";

const SESSION_ID_KEY = "illiniguide.sessionId";
const STUDENT_TYPE_KEY = "illiniguide.studentType";

interface UseSessionResult {
  sessionId: string | null;
  studentType: StudentType | null;
  isReady: boolean;
  isStarting: boolean;
  error: string | null;
  startSession: (studentType: StudentType | null) => Promise<void>;
  // Re-attempts startSession with whichever student type was last tried, so
  // a failed start can be recovered from a "Retry" button instead of only a
  // full page reload.
  retry: () => Promise<void>;
  resetSession: () => void;
}

export function useSession(): UseSessionResult {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [studentType, setStudentType] = useState<StudentType | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAttemptedType, setLastAttemptedType] = useState<StudentType | null>(null);
  // Avoids a hydration mismatch: localStorage isn't available during SSR, so
  // the first client render must also report "no session yet" until this
  // effect has actually had a chance to read it.
  const [hydrated, setHydrated] = useState(false);

  // Syncing from localStorage (an external system, unavailable during SSR)
  // after mount -- a lazy useState initializer would read it during the
  // client's first render too, but that would then mismatch the
  // server-rendered HTML (which always sees no localStorage) and trigger a
  // hydration error. This effect-based sync is the standard tradeoff, so
  // the lint rule is disabled for this whole effect rather than fought.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const storedId = localStorage.getItem(SESSION_ID_KEY);
    const storedType = localStorage.getItem(STUDENT_TYPE_KEY) as StudentType | null;
    if (storedId) {
      setSessionId(storedId);
      setStudentType(storedType);
    }
    setHydrated(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const startSession = useCallback(async (selected: StudentType | null) => {
    setLastAttemptedType(selected);
    setIsStarting(true);
    setError(null);
    try {
      const session = await createSession({ student_type: selected });
      localStorage.setItem(SESSION_ID_KEY, session.id);
      if (selected) {
        localStorage.setItem(STUDENT_TYPE_KEY, selected);
      }
      setSessionId(session.id);
      setStudentType(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start a session.");
    } finally {
      setIsStarting(false);
    }
  }, []);

  const retry = useCallback(
    () => startSession(lastAttemptedType),
    [startSession, lastAttemptedType],
  );

  const resetSession = useCallback(() => {
    localStorage.removeItem(SESSION_ID_KEY);
    localStorage.removeItem(STUDENT_TYPE_KEY);
    setSessionId(null);
    setStudentType(null);
  }, []);

  return {
    sessionId: hydrated ? sessionId : null,
    studentType,
    isReady: hydrated,
    isStarting,
    error,
    startSession,
    retry,
    resetSession,
  };
}
