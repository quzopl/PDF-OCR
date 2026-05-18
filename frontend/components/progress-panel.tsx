"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { JobState } from "@/lib/types";

const STAGE_LABEL: Record<JobState["stage"], string> = {
  queued: "Queued",
  downloading_models: "Downloading models",
  preprocessing: "Preparing pages",
  ocr: "Running OCR",
  formatting: "Building outputs",
  finished: "Finished",
};

export function ProgressPanel({ state }: { state: JobState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Progress</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Progress value={state.progress_pct} />
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>{STAGE_LABEL[state.stage] ?? state.stage}</span>
          <span>
            {state.pages_done} / {state.total_pages} pages
            {state.active_workers > 0 && ` · ${state.active_workers} workers`}
          </span>
        </div>
        {state.warnings.length > 0 && (
          <ul className="text-xs text-amber-500 list-disc pl-4">
            {state.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
