#!/usr/bin/env python3
"""Choose a local Gemma 4 model from installed system RAM.

The selector intentionally returns only Gemma 4 Ollama tags. It uses conservative
RAM bands because the operating system, Ollama runtime, context cache, and other
applications also need memory.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import platform
import subprocess
import sys

MODELS = [
    (48, "gemma4:31b", "48 GB or more"),
    (32, "gemma4:26b", "32–47 GB"),
    (24, "gemma4:12b", "24–31 GB"),
    (16, "gemma4:e4b", "16–23 GB"),
    (0, "gemma4:e2b", "under 16 GB"),
]


def total_memory_gb() -> float:
    """Return physical RAM in GiB, with OS-specific fallbacks."""
    if platform.system() == "Windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / (1024 ** 3)

    if platform.system() == "Darwin":
        try:
            value = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return int(value) / (1024 ** 3)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    try:
        with open("/proc/meminfo", encoding="ascii") as meminfo:
            for line in meminfo:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except (OSError, ValueError):
        pass

    # POSIX fallback (pages * page size).
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 ** 3)
    except (ValueError, OSError, AttributeError):
        raise RuntimeError("Could not detect system RAM on this computer.")


def choose_model(ram_gb: float) -> str:
    for minimum, model, _ in MODELS:
        if ram_gb >= minimum:
            return model
    return "gemma4:e2b"


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a Gemma 4 Ollama model using system RAM.")
    parser.add_argument("--model-only", action="store_true", help="Print only the selected model tag.")
    args = parser.parse_args()
    try:
        ram = total_memory_gb()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    model = choose_model(ram)
    if args.model_only:
        print(model)
    else:
        band = next(label for minimum, tag, label in MODELS if tag == model)
        print(f"Detected {ram:.1f} GiB of system RAM.")
        print(f"Selected {model} ({band})")
        print("Only Gemma 4 models are selected by this launcher.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
