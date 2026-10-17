"""Relevés de l'hôte Proxmox : température et charge CPU, RAM, état des LXC."""
from __future__ import annotations

import glob
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class LxcState:
    running: int = 0
    expected: int = 0          # LXC avec onboot: 1
    down: list[str] = field(default_factory=list)  # attendus mais arrêtés

    @property
    def ok(self) -> bool:
        return not self.down


def _hwmon(name: str) -> str | None:
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if open(f"{path}/name").read().strip() == name:
                return path
        except OSError:
            continue
    return None


_K10 = _hwmon("k10temp")


def cpu_temp() -> float | None:
    """Tctl du Ryzen (k10temp)."""
    if not _K10:
        return None
    try:
        return int(open(f"{_K10}/temp1_input").read()) / 1000
    except OSError:
        return None


class CpuLoad:
    """Charge CPU globale, calculée entre deux appels (/proc/stat)."""

    def __init__(self):
        self._prev = self._read()

    @staticmethod
    def _read() -> tuple[int, int]:
        f = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        idle = f[3] + f[4]
        return idle, sum(f)

    def percent(self) -> float:
        idle, total = self._read()
        d_idle, d_total = idle - self._prev[0], total - self._prev[1]
        self._prev = (idle, total)
        return 0.0 if d_total <= 0 else 100 * (1 - d_idle / d_total)


def ram() -> tuple[float, float]:
    """(utilisée, totale) en Go."""
    info = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    total = info["MemTotal"] / 1024 ** 2
    used = total - info["MemAvailable"] / 1024 ** 2
    return used, total


def lxc_state() -> LxcState:
    """État des LXC : un LXC « attendu » est un LXC avec onboot: 1."""
    onboot = set()
    for conf in glob.glob("/etc/pve/lxc/*.conf"):
        try:
            text = open(conf).read().split("\n[", 1)[0]  # hors snapshots
        except OSError:
            continue
        if re.search(r"^onboot:\s*1\s*$", text, re.M):
            onboot.add(conf.rsplit("/", 1)[1][:-5])
    state = LxcState(expected=len(onboot))
    out = subprocess.run(["pct", "list"], capture_output=True, text=True, timeout=10).stdout
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        vmid, status, name = parts[0], parts[1], parts[-1]
        if status == "running":
            state.running += 1
        elif vmid in onboot:
            state.down.append(f"{vmid} {name}")
    return state
