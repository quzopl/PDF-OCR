"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { Dropzone } from "@/components/dropzone";
import { HardwareChip } from "@/components/hardware-chip";
import { JobOptions } from "@/components/job-options";
import { ProgressPanel } from "@/components/progress-panel";
import { ResultsPanel } from "@/components/results-panel";
import { UnlockPanel } from "@/components/unlock-panel";
import { useJobStatus } from "@/hooks/use-job-status";
import { createJob, getSystemInfo } from "@/lib/api";
import type { JobRequest, SystemInfo, UploadResponse } from "@/lib/types";

export default function Page() {
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { state, error } = useJobStatus(jobId);

  useEffect(() => {
    getSystemInfo().then(setSystem).catch(() => setSystem(null));
  }, []);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  useEffect(() => {
    if (state?.status === "failed" && state.error) toast.error(state.error.message);
  }, [state]);

  const handleSubmit = async (req: JobRequest) => {
    setSubmitting(true);
    try {
      const { job_id } = await createJob(req);
      setJobId(job_id);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUploaded = (resp: UploadResponse) => {
    setUpload(resp);
    setJobId(null);
  };

  const defaultWorkers = system?.cpu.count ?? 1;

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">OCR PDF</h1>
        <HardwareChip />
      </header>

      <Dropzone onUploaded={handleUploaded} disabled={state?.status === "running"} />

      <AnimatePresence>
        {upload?.is_encrypted && (
          <motion.div
            key="unlock"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <UnlockPanel fileId={upload.file_id} onUnlocked={setUpload} />
          </motion.div>
        )}

        {upload && !upload.is_encrypted && (
          <motion.div
            key="opts"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <JobOptions
              fileId={upload.file_id}
              pageCount={upload.page_count}
              system={system}
              defaultWorkers={defaultWorkers}
              onSubmit={handleSubmit}
              submitting={submitting || state?.status === "running"}
            />
          </motion.div>
        )}

        {state && state.status !== "done" && (
          <motion.div
            key="prog"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <ProgressPanel state={state} />
          </motion.div>
        )}

        {state?.status === "done" && (
          <motion.div
            key="res"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <ResultsPanel state={state} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
