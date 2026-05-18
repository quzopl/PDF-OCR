import type { Engine, OutputFormat } from "@/lib/types";

type Quality = "native" | "derived";

const MATRIX: Record<Engine, Record<OutputFormat, Quality>> = {
  ocrmypdf: { pdf: "native", txt: "native", md: "derived", docx: "derived", json: "derived" },
  paddle:   { pdf: "derived", txt: "derived", md: "derived", docx: "derived", json: "native" },
};

const WARNINGS: Partial<Record<Engine, Partial<Record<OutputFormat, string>>>> = {
  ocrmypdf: {
    json: "JSON positions for OCRmyPDF are extracted from the text layer (less precise than Paddle's native boxes).",
    md: "Markdown structure is approximate; no heading/table detection.",
    docx: "DOCX layout is paragraph-only; no formatting recovery.",
  },
  paddle: {
    pdf: "Searchable PDF for PaddleOCR is built by overlaying invisible text on the original pages.",
    md: "Markdown structure is approximate; no heading/table detection.",
    docx: "DOCX layout is paragraph-only; no formatting recovery.",
  },
};

export function formatQuality(engine: Engine, fmt: OutputFormat): Quality {
  return MATRIX[engine][fmt];
}

export function formatWarning(engine: Engine, fmt: OutputFormat): string | null {
  return WARNINGS[engine]?.[fmt] ?? null;
}
