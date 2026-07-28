#!/usr/bin/env python3
"""Smoke test del ProcessWatcher.

Lanza una serie de escenarios minimos contra el engine directo (sin MCP) para
verificar que el pipeline spawn -> pattern match -> persistencia -> kill funciona.

Uso:
    python .agent/scripts/watcher-smoke.py

Salida: 0 si todos pasan, 1 si alguno fallo.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

_agent_dir = Path(__file__).resolve().parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from core.process_watcher import (  # noqa: E402
    Pattern,
    ProcessWatcher,
    TooManyWatchesError,
    WatcherConfig,
    WatcherError,
)


def _make_watcher(tmp: Path, **cfg) -> ProcessWatcher:
    return ProcessWatcher(
        tmp / "state.db",
        config=WatcherConfig(
            enable_gateway_notify=False,
            enable_brain_ingest=False,
            **cfg,
        ),
    )


def scenario_simple_match(tmp: Path) -> None:
    w = _make_watcher(tmp)
    cmd = f"{sys.executable} -c \"print('HELLO WORLD')\""
    wid = w.spawn(
        cmd,
        patterns=[Pattern(regex=r"HELLO", label="hello match", importance="high")],
    )
    _wait_exit(w, wid, timeout=5.0)
    status = w.status(wid)
    assert status["state"] == "exited", f"state esperado exited, got {status['state']}"
    assert status["match_count"] == 1, f"match_count esperado 1, got {status['match_count']}"
    matches = w.matches(wid)
    assert len(matches) == 1 and matches[0]["pattern_label"] == "hello match"


def scenario_multiline_output(tmp: Path) -> None:
    w = _make_watcher(tmp)
    script = (
        "import time;"
        "print('line 1');"
        "print('ERROR: something failed');"
        "print('line 3');"
        "print('OK done')"
    )
    cmd = f'{sys.executable} -c "{script}"'
    wid = w.spawn(
        cmd,
        patterns=[
            Pattern(regex=r"^ERROR:", label="error line", importance="critical"),
            Pattern(regex=r"OK done", label="success", importance="high"),
        ],
    )
    _wait_exit(w, wid, timeout=5.0)
    status = w.status(wid)
    assert status["match_count"] == 2, f"esperado 2, got {status['match_count']}"
    labels = {m["pattern_label"] for m in w.matches(wid)}
    assert labels == {"error line", "success"}


def scenario_stderr_matching(tmp: Path) -> None:
    w = _make_watcher(tmp)
    cmd = f"{sys.executable} -c \"import sys; print('boom', file=sys.stderr)\""
    wid = w.spawn(
        cmd,
        patterns=[Pattern(regex=r"boom", label="stderr boom", importance="high")],
    )
    _wait_exit(w, wid, timeout=5.0)
    matches = w.matches(wid)
    assert len(matches) == 1 and matches[0]["stream"] == "stderr"


def scenario_kill_long_running(tmp: Path) -> None:
    w = _make_watcher(tmp)
    cmd = f'{sys.executable} -c "import time; time.sleep(60)"'
    wid = w.spawn(cmd, patterns=[])
    time.sleep(0.3)
    status_before = w.status(wid)
    assert status_before["state"] == "running"
    killed = w.kill(wid)
    assert killed, "kill debio devolver True"
    time.sleep(0.3)
    status_after = w.status(wid)
    assert status_after["state"] == "killed", f"got {status_after['state']}"


def scenario_invalid_regex(tmp: Path) -> None:
    w = _make_watcher(tmp)
    try:
        w.spawn(
            "echo x",
            patterns=[Pattern(regex="(unclosed", label="broken", importance="low")],
        )
    except WatcherError:
        return
    raise AssertionError("regex invalida debio levantar WatcherError")


def scenario_max_watches(tmp: Path) -> None:
    w = _make_watcher(tmp, max_watches=2)
    cmd = f'{sys.executable} -c "import time; time.sleep(10)"'
    wid1 = w.spawn(cmd, patterns=[])
    wid2 = w.spawn(cmd, patterns=[])
    try:
        w.spawn(cmd, patterns=[])
    except TooManyWatchesError:
        pass
    else:
        raise AssertionError("debio levantar TooManyWatchesError")
    finally:
        w.kill(wid1)
        w.kill(wid2)


def scenario_tail_and_stats(tmp: Path) -> None:
    w = _make_watcher(tmp)
    script = ";".join(f"print('line {i}')" for i in range(1, 11))
    cmd = f'{sys.executable} -c "{script}"'
    wid = w.spawn(cmd, patterns=[Pattern(regex=r"line 5", label="mid", importance="low")])
    _wait_exit(w, wid, timeout=5.0)
    # tail no esta disponible despues de exit, pero stats/matches si
    stats = w.stats()
    assert stats["total_watches"] >= 1
    matches = w.matches(wid)
    assert len(matches) == 1 and matches[0]["line_number"] == 5


def scenario_unknown_watch(tmp: Path) -> None:
    w = _make_watcher(tmp)
    try:
        w.status("w-does-not-exist")
    except WatcherError:
        return
    raise AssertionError("status con watch_id inexistente debio fallar")


def scenario_cleanup_noop(tmp: Path) -> None:
    w = _make_watcher(tmp, ttl_seconds=0)
    cmd = f"{sys.executable} -c \"print('quick')\""
    wid = w.spawn(cmd, patterns=[])
    _wait_exit(w, wid, timeout=5.0)
    time.sleep(1.1)
    removed = w.cleanup_expired()
    assert removed >= 1, f"cleanup debio remover >=1, got {removed}"


def _wait_exit(w: ProcessWatcher, wid: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = w.status(wid).get("state")
        except WatcherError:
            return
        if state in {"exited", "killed", "error"}:
            return
        time.sleep(0.05)
    raise AssertionError(f"timeout esperando fin de {wid}")


SCENARIOS = [
    ("simple_match", scenario_simple_match),
    ("multiline_output", scenario_multiline_output),
    ("stderr_matching", scenario_stderr_matching),
    ("kill_long_running", scenario_kill_long_running),
    ("invalid_regex", scenario_invalid_regex),
    ("max_watches", scenario_max_watches),
    ("tail_and_stats", scenario_tail_and_stats),
    ("unknown_watch", scenario_unknown_watch),
    ("cleanup_noop", scenario_cleanup_noop),
]


def main() -> int:
    passed = 0
    failed: list[tuple[str, str]] = []
    for name, fn in SCENARIOS:
        with tempfile.TemporaryDirectory(prefix="watcher-smoke-") as tmp:
            try:
                fn(Path(tmp))
                print(f"[OK]   {name}")
                passed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[FAIL] {name}: {exc}")
                failed.append((name, str(exc)))
    total = len(SCENARIOS)
    print(f"\nResultado: {passed}/{total} escenarios OK")
    if failed:
        for name, err in failed:
            print(f"  - {name}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
