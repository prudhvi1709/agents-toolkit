#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run a long unattended job on macOS without the machine sleeping under it.

Wraps any command with the guardrails an overnight run needs: a preflight that
refuses to start a doomed run, a sleep assertion tied to this process so it
cannot leak, a hard wall-clock deadline, and whole-process-group cleanup.

Exit codes:
  0   the command succeeded
  1   the command failed
  2   usage error
  3   preflight refused to start
  4   the deadline was reached and the command was terminated
  130 interrupted
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path
from types import FrameType

# macOS puts the system to sleep after 1 minute idle on battery by default, so a
# battery run dies almost immediately. AC is a hard requirement unless waived.
DEFAULT_MIN_FREE_GB = 10.0
DEFAULT_GRACE_S = 120
MAX_REASONABLE_HOURS = 48.0


class Exit(IntEnum):
    OK = 0
    COMMAND_FAILED = 1
    USAGE = 2
    PREFLIGHT = 3
    DEADLINE = 4
    INTERRUPTED = 130


@dataclass(frozen=True, slots=True)
class Preflight:
    ok: bool
    checks: tuple[tuple[str, bool, str], ...]

    def render(self) -> str:
        return "\n".join(
            f"  {'ok  ' if passed else 'FAIL'} {name}: {detail}" for name, passed, detail in self.checks
        )


class LockError(RuntimeError):
    """Another run already holds the lock."""


def on_ac_power() -> tuple[bool, str]:
    try:
        out = subprocess.run(
            ["pmset", "-g", "ps"], capture_output=True, text=True, timeout=10, check=True
        ).stdout
    except (subprocess.SubprocessError, OSError) as err:
        return False, f"could not read power source: {err}"
    first = out.splitlines()[0] if out.strip() else ""
    return ("AC Power" in first), first.strip() or "unknown"


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1024**3


def acquire_lock(lock: Path) -> None:
    """Create a pid lockfile, reclaiming it if the recorded process is gone."""
    if lock.exists():
        raw = lock.read_text(encoding="utf-8").strip()
        pid = int(raw) if raw.isdigit() else None
        if pid is not None:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass  # stale lock, the owner died
            except PermissionError as err:
                raise LockError(f"lock held by pid {pid} owned by another user") from err
            else:
                raise LockError(f"another run is active (pid {pid}, lock {lock})")
        lock.unlink(missing_ok=True)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")


def resolve_deadline(until: str | None, max_hours: float | None) -> datetime:
    now = datetime.now()
    if until is not None:
        try:
            hh, mm = (int(part) for part in until.split(":", 1))
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        except ValueError as err:
            raise ValueError(f"--until must be HH:MM, got {until!r}") from err
        if target <= now:
            target += timedelta(days=1)
        return target
    return now + timedelta(hours=max_hours if max_hours is not None else 8.0)


def preflight(
    *, workdir: Path, deadline: datetime, min_free: float, allow_battery: bool, lock: Path
) -> Preflight:
    checks: list[tuple[str, bool, str]] = []

    ac, source = on_ac_power()
    checks.append(
        ("power", ac or allow_battery, source + (" (battery waived)" if not ac and allow_battery else ""))
    )

    free = free_gb(workdir)
    checks.append(("disk", free >= min_free, f"{free:.1f} GB free, need {min_free:.1f} GB"))

    hours = (deadline - datetime.now()).total_seconds() / 3600
    sane = 0 < hours <= MAX_REASONABLE_HOURS
    checks.append(("deadline", sane, f"{deadline:%Y-%m-%d %H:%M} ({hours:.1f}h from now)"))

    try:
        acquire_lock(lock)
    except LockError as err:
        checks.append(("lock", False, str(err)))
    except OSError as err:
        checks.append(("lock", False, f"could not write {lock}: {err}"))
    else:
        checks.append(("lock", True, str(lock)))

    checks.append(("caffeinate", shutil.which("caffeinate") is not None, "/usr/bin/caffeinate"))

    return Preflight(ok=all(passed for _, passed, _ in checks), checks=tuple(checks))


def start_caffeinate(*, keep_display_awake: bool) -> subprocess.Popen[bytes] | None:
    """Hold a sleep assertion bound to this process, so it cannot outlive us.

    -i blocks idle sleep, -m blocks disk sleep, -w ties the assertion to our pid
    so caffeinate exits even if this process is killed with SIGKILL.
    """
    flags = ["-i", "-m"] + (["-d"] if keep_display_awake else [])
    try:
        return subprocess.Popen(["caffeinate", *flags, "-w", str(os.getpid())])
    except OSError as err:
        print(f"warning: could not start caffeinate: {err}", file=sys.stderr)
        return None


def terminate_group(proc: subprocess.Popen[str], grace: int) -> None:
    """Stop the command and everything it spawned, escalating if it ignores us."""
    if proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 30)):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def run_command(
    command: list[str], *, workdir: Path, log_path: Path, deadline: datetime, grace: int
) -> tuple[int, bool]:
    """Stream the command to console and log. Returns (returncode, hit_deadline)."""
    hit_deadline = threading.Event()
    stopping = threading.Event()

    proc = subprocess.Popen(
        command,
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,  # own process group, so cleanup reaches grandchildren
    )

    def watchdog() -> None:
        remaining = (deadline - datetime.now()).total_seconds()
        if stopping.wait(timeout=max(remaining, 0)):
            return
        hit_deadline.set()
        print(f"\n[{datetime.now():%H:%M:%S}] deadline reached, terminating", flush=True)
        terminate_group(proc, grace)

    def on_signal(signum: int, _frame: FrameType | None) -> None:
        print(f"\n[{datetime.now():%H:%M:%S}] got signal {signum}, terminating", flush=True)
        stopping.set()
        terminate_group(proc, grace)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, on_signal)

    timer = threading.Thread(target=watchdog, daemon=True)
    timer.start()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} started: {' '.join(command)}\n")
        log.flush()
        if proc.stdout is not None:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
        code = proc.wait()
        log.write(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} exited rc={code}\n")

    stopping.set()
    return code, hit_deadline.is_set()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caffeinate.py",
        description="Run a long unattended job without the Mac sleeping under it.",
        epilog=(
            "examples:\n"
            "  caffeinate.py --until 07:00 -- python3 pipeline/overnight.py --run\n"
            "  caffeinate.py --max-hours 6 --dry-run -- ./crawl.sh\n"
            "  caffeinate.py --until 06:30 --output json -- make nightly\n\n"
            "exit codes: 0 ok, 1 command failed, 2 usage, 3 preflight refused,\n"
            "            4 deadline reached, 130 interrupted"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    parser.add_argument("--until", metavar="HH:MM", help="stop at this clock time (next occurrence)")
    parser.add_argument("--max-hours", type=float, help="stop after this many hours (default 8)")
    parser.add_argument("--workdir", type=Path, default=Path.cwd(), help="working directory")
    parser.add_argument("--log", type=Path, help="log file (default: WORKDIR/logs/caffeinate-STAMP.log)")
    parser.add_argument(
        "--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB, help="required free disk space"
    )
    parser.add_argument(
        "--allow-battery", action="store_true", help="proceed on battery (the run will likely die)"
    )
    parser.add_argument(
        "--keep-display-awake", action="store_true", help="also block display sleep (uses more power)"
    )
    parser.add_argument(
        "--grace", type=int, default=DEFAULT_GRACE_S, help="seconds between SIGTERM and SIGKILL"
    )
    parser.add_argument("--dry-run", action="store_true", help="run preflight, print the plan, exit")
    parser.add_argument("--output", choices=("text", "json"), default="text", help="summary format")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]  # only the separator, so "git log -- path" survives
    if not command:
        parser.error("no command given; put it after --")
    if args.until and args.max_hours:
        parser.error("use --until or --max-hours, not both")

    workdir = args.workdir.expanduser().resolve()
    if not workdir.is_dir():
        parser.error(f"not a directory: {workdir}")

    try:
        deadline = resolve_deadline(args.until, args.max_hours)
    except ValueError as err:
        parser.error(str(err))

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = (args.log or workdir / "logs" / f"caffeinate-{stamp}.log").expanduser()
    lock = workdir / ".caffeinate.lock"

    checks = preflight(
        workdir=workdir,
        deadline=deadline,
        min_free=args.min_free_gb,
        allow_battery=args.allow_battery,
        lock=lock,
    )
    print(f"preflight for: {' '.join(command)}")
    print(checks.render())

    if not checks.ok:
        # The lock may have been taken before a later check failed; do not leave
        # it behind for a run that never started.
        if any(name == "lock" and passed for name, passed, _ in checks.checks):
            lock.unlink(missing_ok=True)
        print("\nrefusing to start. Fix the failures above or waive them explicitly.")
        return Exit.PREFLIGHT
    if args.dry_run:
        print(f"\ndry run: would log to {log_path} and stop by {deadline:%Y-%m-%d %H:%M}")
        lock.unlink(missing_ok=True)
        return Exit.OK

    print(f"\nlogging to {log_path}")
    print(f"deadline  {deadline:%Y-%m-%d %H:%M}\n")

    started = datetime.now()
    keeper = start_caffeinate(keep_display_awake=args.keep_display_awake)
    try:
        code, hit_deadline = run_command(
            command, workdir=workdir, log_path=log_path, deadline=deadline, grace=args.grace
        )
    except KeyboardInterrupt:
        return Exit.INTERRUPTED
    finally:
        if keeper is not None:
            keeper.terminate()
        lock.unlink(missing_ok=True)

    ended = datetime.now()
    status = Exit.DEADLINE if hit_deadline else (Exit.OK if code == 0 else Exit.COMMAND_FAILED)
    summary = {
        "command": command,
        "started": started.isoformat(timespec="seconds"),
        "ended": ended.isoformat(timespec="seconds"),
        "duration_hours": round((ended - started).total_seconds() / 3600, 2),
        "returncode": code,
        "hit_deadline": hit_deadline,
        "log": str(log_path),
        "exit": int(status),
    }
    if args.output == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"\nran {summary['duration_hours']}h, rc={code}"
            f"{', stopped at deadline' if hit_deadline else ''}\nlog: {log_path}"
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
