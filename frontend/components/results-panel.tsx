"use client";

import { Download } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { downloadUrl } from "@/lib/api";
import type { JobState, OutputFormat } from "@/lib/types";

const LABELS: Record<OutputFormat, string> = {
  pdf: "PDF",
  txt: "TXT",
  md: "Markdown",
  docx: "DOCX",
  json: "JSON",
};

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ResultsPanel({ state }: { state: JobState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Download</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        {state.outputs.map((o) => (
          <a
            key={o.format}
            href={downloadUrl(state.job_id, o.format)}
            download
            className={cn(buttonVariants({ variant: "outline" }))}
          >
            <Download className="h-4 w-4 mr-2" />
            {LABELS[o.format]}
            <span className="ml-2 text-xs text-muted-foreground">{fmtSize(o.size_bytes)}</span>
          </a>
        ))}
      </CardContent>
    </Card>
  );
}
