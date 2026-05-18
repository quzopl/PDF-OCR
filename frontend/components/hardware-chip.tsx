"use client";

import { useEffect, useState } from "react";
import { Cpu, MemoryStick, Zap } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { getSystemInfo } from "@/lib/api";
import type { SystemInfo } from "@/lib/types";

export function HardwareChip() {
  const [info, setInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    getSystemInfo().then(setInfo).catch(() => setInfo(null));
  }, []);

  if (!info) {
    return (
      <div className="text-xs text-muted-foreground px-2 py-1 rounded-full border">
        detecting hardware…
      </div>
    );
  }

  const cuda = info.gpu.cuda_available;
  const gpuLabel = info.gpu.devices[0]?.name ?? "no GPU";

  return (
    <Popover>
      <PopoverTrigger
        className="text-xs px-3 py-1.5 rounded-full border flex items-center gap-3 hover:bg-accent transition-colors"
        aria-label="Hardware info"
      >
          <span className="flex items-center gap-1">
            <Cpu className="h-3.5 w-3.5" />
            {info.cpu.count}
          </span>
          <span className="flex items-center gap-1">
            <MemoryStick className="h-3.5 w-3.5" />
            {Math.round(info.ram.total_gb)} GB
          </span>
          <span className="flex items-center gap-1">
            <Zap className={`h-3.5 w-3.5 ${cuda ? "text-green-500" : "text-muted-foreground"}`} />
            {cuda ? gpuLabel : "CPU only"}
          </span>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 text-sm space-y-2">
        <div>
          <div className="font-medium">CPU</div>
          <div className="text-muted-foreground">
            {info.cpu.count} cores · {info.cpu.model}
          </div>
        </div>
        <div>
          <div className="font-medium">RAM</div>
          <div className="text-muted-foreground">
            {info.ram.available_gb.toFixed(1)} GB free / {info.ram.total_gb.toFixed(1)} GB total
          </div>
        </div>
        <div>
          <div className="font-medium">GPU</div>
          {info.gpu.devices.length === 0 ? (
            <div className="text-muted-foreground">no GPU detected</div>
          ) : (
            <ul className="text-muted-foreground">
              {info.gpu.devices.map((d) => (
                <li key={d.id}>
                  {d.name} · {d.vram_gb} GB · driver {d.driver}
                </li>
              ))}
            </ul>
          )}
          <div className="text-muted-foreground">
            {info.gpu.paddle_gpu_installed
              ? "paddlepaddle-gpu installed"
              : "paddlepaddle-gpu not installed (CPU only)"}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
