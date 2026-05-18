"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { FileText, Upload } from "lucide-react";
import { toast } from "sonner";
import { uploadPdf } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";

interface Props {
  onUploaded: (resp: UploadResponse, file: File) => void;
  disabled?: boolean;
}

export function Dropzone({ onUploaded, disabled }: Props) {
  const [busy, setBusy] = useState(false);
  const [filename, setFilename] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;
      setBusy(true);
      setFilename(file.name);
      try {
        const resp = await uploadPdf(file);
        onUploaded(resp, file);
      } catch (e) {
        toast.error((e as Error).message);
        setFilename(null);
      } finally {
        setBusy(false);
      }
    },
    [onUploaded],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: disabled || busy,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rootProps = getRootProps() as any;

  return (
    <motion.div
      {...rootProps}
      initial={false}
      animate={{ scale: isDragActive ? 1.01 : 1 }}
      className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
        ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <input {...getInputProps()} aria-label="Choose PDF file" />
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        {filename ? (
          <>
            <FileText className="h-10 w-10 text-primary" />
            <div className="text-sm">{filename}</div>
            <div className="text-xs">{busy ? "Uploading…" : "Drop another to replace"}</div>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10" />
            <div className="text-base">Drop your PDF here</div>
            <div className="text-xs">or click to browse</div>
          </>
        )}
      </div>
    </motion.div>
  );
}
