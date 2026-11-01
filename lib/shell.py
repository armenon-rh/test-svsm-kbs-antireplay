"""Thin subprocess helpers: foreground commands, backgrounded daemons, log tailing."""
import os
import re
import signal
import subprocess
import time
from pathlib import Path


class CommandError(RuntimeError):
    def __init__(self, cmd, returncode, output):
        super().__init__(f"command failed ({returncode}): {' '.join(map(str, cmd))}\n{output}")
        self.cmd = cmd
        self.returncode = returncode
        self.output = output


def run(cmd, cwd=None, env=None, check=True):
    printable = " ".join(map(str, cmd))
    print(f"+ {printable}" + (f"  (cwd={cwd})" if cwd else ""))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and proc.returncode != 0:
        raise CommandError(cmd, proc.returncode, proc.stdout)
    return proc


def run_bg(cmd, cwd=None, env=None, log_file=None):
    """Start a long-running process in its own session so stop() can reliably
    kill the whole process group (QEMU in particular spawns helper threads/
    children that a plain terminate() on the launching shell script would miss).
    """
    printable = " ".join(map(str, cmd))
    print(f"+ (bg) {printable}" + (f"  (cwd={cwd})" if cwd else ""))
    log_fh = open(log_file, "wb") if log_file else subprocess.DEVNULL
    return subprocess.Popen(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def stop_bg(proc, timeout=20):
    if proc is None or proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(pgid, signal.SIGKILL)
        proc.wait(timeout=5)
    except ProcessLookupError:
        pass


def wait_for_log_line(path, pattern, timeout):
    """Poll `path` for a line matching `pattern` (regex), returning the matched line."""
    deadline = time.monotonic() + timeout
    regex = re.compile(pattern)
    pos = 0
    path = Path(path)
    while time.monotonic() < deadline:
        if path.exists():
            with open(path, errors="replace") as fh:
                fh.seek(pos)
                for line in fh:
                    if regex.search(line):
                        return line
                pos = fh.tell()
        time.sleep(1)
    raise TimeoutError(f"timed out after {timeout}s waiting for /{pattern}/ in {path}")
