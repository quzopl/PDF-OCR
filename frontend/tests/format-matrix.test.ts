import { describe, expect, it } from "vitest";
import { formatQuality, formatWarning } from "@/lib/format-matrix";

describe("format-matrix", () => {
  it("ranks JSON higher for paddle than ocrmypdf", () => {
    expect(formatQuality("paddle", "json")).toBe("native");
    expect(formatQuality("ocrmypdf", "json")).toBe("derived");
  });

  it("ranks searchable PDF native for ocrmypdf", () => {
    expect(formatQuality("ocrmypdf", "pdf")).toBe("native");
    expect(formatQuality("paddle", "pdf")).toBe("derived");
  });

  it("emits a warning string for derived formats", () => {
    expect(formatWarning("ocrmypdf", "json")).toMatch(/extracted/i);
    expect(formatWarning("paddle", "json")).toBeNull();
  });
});
