"""Bounded child shutdown and health recovery, independent of Soloist internals."""
from dataclasses import dataclass
import os
import selectors
import subprocess
import time


@dataclass(frozen=True)
class Exit:
    code: int
    reason: str
    forced: bool


def run_child(command, environment, stop, deadline, consume, *, started=None,
              health=None, startup_grace=30, health_interval=10, shutdown_grace=15):
    """Never restart here. Caller owns retry policy and scoped sidecar lifetime."""
    with subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, start_new_session=True) as child:
        pending = b""
        reason = "exit"
        stopping_at = None
        exited_at = None
        forced = False
        health_failures = 0
        next_health = time.monotonic() + startup_grace
        try:
            if started:
                started(child.pid)
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                while selector.get_map() or child.poll() is None:
                    now = time.monotonic()
                    if child.poll() is not None:
                        exited_at = exited_at or now
                        # A forked descendant must not keep us waiting forever
                        # merely by inheriting stdout after the receiver exits.
                        if now - exited_at >= 2:
                            break
                    elif stopping_at is None:
                        if stop.is_set():
                            reason = "requested"
                        elif deadline is not None and now >= deadline:
                            reason = "duration"
                        elif health and now >= next_health:
                            try:
                                healthy = health()
                            except Exception:
                                healthy = False
                            health_failures = 0 if healthy else health_failures + 1
                            next_health = time.monotonic() + health_interval
                            if health_failures >= 3:
                                reason = "health"
                        if reason != "exit":
                            stopping_at = time.monotonic()
                            child.terminate()
                    elif now - stopping_at >= shutdown_grace and not forced:
                        forced = True
                        child.kill()
                    for key, _ in selector.select(0.1):
                        block = os.read(key.fd, 8192)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        pending += block
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            consume(line)
                        if len(pending) > 1024 * 1024:
                            raise RuntimeError("Oversized diagnostic line; withheld")
            if pending:
                consume(pending)
            return Exit(child.wait(timeout=shutdown_grace), reason, forced)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=shutdown_grace)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def retry_delay(result, attempt, limit, stopping):
    """Finite lifetime retry budget; do not loop on expired builds or clean exits."""
    if stopping or result.reason in ("requested", "duration") or result.code == 10:
        return None
    if result.code == 0 and result.reason != "health":
        return None
    if attempt >= limit:
        return None
    return min(2 ** (attempt + 1), 30)
