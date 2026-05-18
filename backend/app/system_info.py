from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from importlib.util import find_spec
from typing import Any

import psutil


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def _detect_paddle_gpu() -> bool:
    return find_spec("paddle") is not None and _paddle_cuda_compiled()


def _paddle_cuda_compiled() -> bool:
    try:
        import paddle  # type: ignore

        return bool(paddle.device.is_compiled_with_cuda())
    except Exception:
        return False


def _detect_gpus() -> list[dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []
    devices: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            devices.append(
                {
                    "id": int(parts[0]),
                    "name": parts[1],
                    "vram_gb": round(int(parts[2]) / 1024, 2),
                    "driver": parts[3],
                }
            )
        except ValueError:
            continue
    return devices


@lru_cache(maxsize=1)
def get_system_info() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    devices = _detect_gpus()
    paddle_gpu = _detect_paddle_gpu()
    return {
        "cpu": {
            "count": os.cpu_count() or 1,
            "model": _cpu_model(),
        },
        "ram": {
            "total_gb": round(vm.total / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
        },
        "gpu": {
            "cuda_available": bool(devices) and paddle_gpu,
            "devices": devices,
            "paddle_gpu_installed": paddle_gpu,
        },
    }
