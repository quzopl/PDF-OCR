import { expect, test } from "@playwright/test";
import path from "node:path";

test("upload → ocr → download", async ({ page }) => {
  await page.goto("/");
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(path.join(__dirname, "fixtures", "sample.pdf"));

  await expect(page.getByText("Options")).toBeVisible();
  // Ensure English is selected
  const en = page.locator('label', { hasText: "English" }).locator('button[role="checkbox"]');
  const enChecked = await en.getAttribute("aria-checked");
  if (enChecked !== "true") await en.click();

  await page.getByRole("button", { name: /start ocr/i }).click();
  await expect(page.getByText("Download")).toBeVisible({ timeout: 120_000 });

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /TXT/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.txt$/);
});
