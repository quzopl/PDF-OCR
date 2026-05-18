"use client";

import { useEffect, useMemo, useState } from "react";
import { Cpu, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatWarning } from "@/lib/format-matrix";
import type {
  Device,
  Engine,
  JobRequest,
  Language,
  OutputFormat,
  SystemInfo,
} from "@/lib/types";

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "pl", label: "Polish" },
  { value: "en", label: "English" },
  { value: "de", label: "German" },
  { value: "fr", label: "French" },
  { value: "es", label: "Spanish" },
  { value: "ru", label: "Russian" },
];

const FORMATS: { value: OutputFormat; label: string }[] = [
  { value: "pdf", label: "Searchable PDF" },
  { value: "txt", label: "Plain text" },
  { value: "md", label: "Markdown" },
  { value: "docx", label: "DOCX" },
  { value: "json", label: "JSON (positions)" },
];

interface Props {
  fileId: string;
  pageCount: number;
  system: SystemInfo | null;
  defaultWorkers: number;
  onSubmit: (req: JobRequest) => void;
  submitting: boolean;
}

export function JobOptions({
  fileId,
  pageCount,
  system,
  defaultWorkers,
  onSubmit,
  submitting,
}: Props) {
  const [engine, setEngine] = useState<Engine>("ocrmypdf");
  const [languages, setLanguages] = useState<Language[]>(["pl", "en"]);
  const [range, setRange] = useState<[number, number]>([1, pageCount]);
  const [deskew, setDeskew] = useState(true);
  const [denoise, setDenoise] = useState(true);
  const [formats, setFormats] = useState<OutputFormat[]>(["pdf", "txt"]);
  const [workers, setWorkers] = useState<number>(defaultWorkers);
  const [device, setDevice] = useState<Device>("cpu");

  useEffect(() => {
    setRange([1, pageCount]);
  }, [pageCount]);

  const cudaAvailable = !!system?.gpu.cuda_available && engine === "paddle";

  useEffect(() => {
    if (!cudaAvailable && device === "cuda") setDevice("cpu");
  }, [cudaAvailable, device]);

  const workerOptions = useMemo(() => {
    const max = system?.cpu.count ?? defaultWorkers;
    const opts = [1, 2, 4, 8, 12, 16, 24, 32].filter((n) => n <= max);
    if (!opts.includes(max)) opts.push(max);
    return Array.from(new Set(opts)).sort((a, b) => a - b);
  }, [system, defaultWorkers]);

  const toggle = <T,>(arr: T[], v: T): T[] =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];

  const canSubmit =
    languages.length > 0 && formats.length > 0 && range[0] >= 1 && range[1] >= range[0];

  const handleSubmit = () => {
    onSubmit({
      file_id: fileId,
      engine,
      languages,
      page_range: range,
      preprocess: { deskew, denoise },
      formats,
      workers,
      device,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Options</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label>Engine</Label>
            <RadioGroup value={engine} onValueChange={(v) => setEngine(v as Engine)}>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="eng-ocr" value="ocrmypdf" />
                <Label htmlFor="eng-ocr">OCRmyPDF (Tesseract)</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="eng-paddle" value="paddle" />
                <Label htmlFor="eng-paddle">PaddleOCR</Label>
              </div>
            </RadioGroup>
          </div>

          <div className="space-y-2">
            <Label>Languages</Label>
            <div className="grid grid-cols-3 gap-2">
              {LANGUAGES.map((l) => (
                <label key={l.value} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={languages.includes(l.value)}
                    onCheckedChange={() => setLanguages(toggle(languages, l.value))}
                  />
                  {l.label}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label>
            Pages: {range[0]} – {range[1]} of {pageCount}
          </Label>
          <Slider
            min={1}
            max={pageCount}
            step={1}
            value={range}
            onValueChange={(v) => {
              const arr = v as readonly number[];
              setRange([arr[0], arr[1]] as [number, number]);
            }}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label>Preprocessing</Label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={deskew} onCheckedChange={(v) => setDeskew(!!v)} />
              Deskew
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={denoise} onCheckedChange={(v) => setDenoise(!!v)} />
              Denoise
            </label>
          </div>

          <div className="space-y-2">
            <Label>Output formats</Label>
            <div className="grid grid-cols-2 gap-2">
              {FORMATS.map((f) => {
                const warn = formatWarning(engine, f.value);
                return (
                  <TooltipProvider key={f.value}>
                    <Tooltip>
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={formats.includes(f.value)}
                          onCheckedChange={() => setFormats(toggle(formats, f.value))}
                        />
                        <TooltipTrigger
                          render={<span />}
                          className={warn ? "underline decoration-dotted cursor-default" : "cursor-default"}
                        >
                          {f.label}
                        </TooltipTrigger>
                      </label>
                      {warn && <TooltipContent>{warn}</TooltipContent>}
                    </Tooltip>
                  </TooltipProvider>
                );
              })}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Cpu className="h-4 w-4" /> Workers
            </Label>
            <Select
              value={String(workers)}
              onValueChange={(v) => { if (v !== null) setWorkers(parseInt(v, 10)); }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {workerOptions.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n === defaultWorkers ? `Auto (${n})` : String(n)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {engine === "paddle" && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Zap className="h-4 w-4" /> Device
              </Label>
              <RadioGroup value={device} onValueChange={(v) => setDevice(v as Device)}>
                <div className="flex items-center gap-2">
                  <RadioGroupItem
                    id="dev-cuda"
                    value="cuda"
                    disabled={!cudaAvailable}
                  />
                  <Label htmlFor="dev-cuda" className={!cudaAvailable ? "opacity-50" : ""}>
                    CUDA{" "}
                    {system?.gpu.devices[0]
                      ? `(${system.gpu.devices[0].name})`
                      : "(unavailable)"}
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="dev-cpu" value="cpu" />
                  <Label htmlFor="dev-cpu">CPU</Label>
                </div>
              </RadioGroup>
            </div>
          )}
        </div>

        <div className="pt-2">
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit} size="lg">
            {submitting ? "Starting…" : "Start OCR"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
