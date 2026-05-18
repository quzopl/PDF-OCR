"use client";

import { useEffect, useRef, useState } from "react";
import { getJob } from "@/lib/api";
import type { JobState } from "@/lib/types";

export function useJobStatus(jobId: string | null, intervalMs = 1000) {
  const [state, setState] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setState(null);
    setError(null);
    const ac = new AbortController();
    abortRef.current = ac;
    let stopped = false;
    const tick = async () => {
      while (!stopped) {
        try {
          const next = await getJob(jobId);
          if (stopped) return;
          setState(next);
          if (next.status === "done" || next.status === "failed") return;
        } catch (e) {
          if (!stopped) setError((e as Error).message);
          return;
        }
        await new Promise((r) => setTimeout(r, intervalMs));
      }
    };
    void tick();
    return () => {
      stopped = true;
      ac.abort();
    };
  }, [jobId, intervalMs]);

  return { state, error, stop: () => abortRef.current?.abort() };
}
