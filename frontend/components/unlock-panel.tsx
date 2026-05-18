"use client";

import { useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { unlockPdf } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";

interface Props {
  fileId: string;
  onUnlocked: (resp: UploadResponse) => void;
}

export function UnlockPanel({ fileId, onUnlocked }: Props) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const resp = await unlockPdf(fileId, password);
      toast.success(`Unlocked — ${resp.page_count} pages`);
      onUnlocked(resp);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lock className="h-5 w-5 text-amber-500" />
          PDF is password-protected
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Enter the password to remove the protection. The PDF will be saved decrypted in
          place and you can proceed with OCR. Leave empty if it has owner-only restrictions.
        </p>
        <div className="space-y-2">
          <Label htmlFor="pdf-password">Password</Label>
          <Input
            id="pdf-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !busy) submit();
            }}
            placeholder="password"
            autoFocus
          />
        </div>
        <Button onClick={submit} disabled={busy}>
          <Unlock className="h-4 w-4 mr-2" />
          {busy ? "Unlocking…" : "Unlock"}
        </Button>
      </CardContent>
    </Card>
  );
}
