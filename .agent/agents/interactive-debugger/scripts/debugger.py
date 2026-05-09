#!/usr/bin/env python3
"""
Interactive Debugger Agent - Debugging interactivo avanzado

Permite pausar, inspeccionar, y hacer time-travel debugging.
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DebugStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"


class BreakpointType(Enum):
    LINE = "line"
    CONDITIONAL = "conditional"
    EXCEPTION = "exception"
    WATCHPOINT = "watchpoint"


@dataclass
class Breakpoint:
    id: str
    file: str
    line: int
    type: BreakpointType = BreakpointType.LINE
    condition: str | None = None
    hit_count: int = 0
    enabled: bool = True


@dataclass
class Watchpoint:
    id: str
    expression: str
    last_value: Any = None
    triggered: bool = False


@dataclass
class StackFrame:
    id: int
    function: str
    file: str
    line: int
    locals: dict = field(default_factory=dict)


@dataclass
class StateSnapshot:
    id: str
    name: str
    timestamp: datetime
    frame_id: int
    locals: dict
    stack_trace: list[StackFrame]


@dataclass
class DebugSession:
    id: str
    target: str
    status: DebugStatus
    breakpoints: list[Breakpoint] = field(default_factory=list)
    watchpoints: list[Watchpoint] = field(default_factory=list)
    snapshots: list[StateSnapshot] = field(default_factory=list)
    current_frame: int = 0
    history: list[dict] = field(default_factory=list)


class InteractiveDebugger:
    """Debugger interactivo con time-travel."""

    def __init__(self):
        self.sessions: dict[str, DebugSession] = {}
        self.current_session: str | None = None
        self.session_counter = 0
        self.breakpoint_counter = 0
        self.snapshot_counter = 0

    def start_session(self, target: str) -> DebugSession:
        """Inicia nueva sesion de debug."""
        self.session_counter += 1
        session_id = f"session_{self.session_counter}"

        session = DebugSession(id=session_id, target=target, status=DebugStatus.IDLE)

        self.sessions[session_id] = session
        self.current_session = session_id
        return session

    def get_current_session(self) -> DebugSession | None:
        """Obtiene sesion actual."""
        if self.current_session:
            return self.sessions.get(self.current_session)
        return None

    def add_breakpoint(self, file: str, line: int, condition: str | None = None) -> Breakpoint:
        """Agrega breakpoint."""
        session = self.get_current_session()
        if not session:
            raise ValueError("No active session")

        self.breakpoint_counter += 1
        bp = Breakpoint(
            id=f"bp_{self.breakpoint_counter}",
            file=file,
            line=line,
            type=BreakpointType.CONDITIONAL if condition else BreakpointType.LINE,
            condition=condition,
        )

        session.breakpoints.append(bp)
        return bp

    def add_watchpoint(self, expression: str) -> Watchpoint:
        """Agrega watchpoint."""
        session = self.get_current_session()
        if not session:
            raise ValueError("No active session")

        wp = Watchpoint(id=f"wp_{len(session.watchpoints) + 1}", expression=expression)

        session.watchpoints.append(wp)
        return wp

    def take_snapshot(self, name: str | None = None) -> StateSnapshot:
        """Toma snapshot del estado actual."""
        session = self.get_current_session()
        if not session:
            raise ValueError("No active session")

        self.snapshot_counter += 1
        snapshot_id = f"snap_{self.snapshot_counter}"

        # Simular estado (en produccion: obtener del debugger real)
        snapshot = StateSnapshot(
            id=snapshot_id,
            name=name or snapshot_id,
            timestamp=datetime.now(),
            frame_id=session.current_frame,
            locals={"x": 42, "user": {"name": "test"}},  # Simulado
            stack_trace=[
                StackFrame(0, "main", "app.py", 10),
                StackFrame(1, "process", "utils.py", 25),
            ],
        )

        session.snapshots.append(snapshot)
        return snapshot

    def time_travel(self, direction: str, steps: int = 1) -> dict:
        """Navega en el historial."""
        session = self.get_current_session()
        if not session:
            return {"error": "No active session"}

        if not session.snapshots:
            return {"error": "No snapshots available"}

        # Simular time travel
        if direction == "back":
            # Ir al snapshot anterior
            idx = max(0, len(session.snapshots) - 1 - steps)
        else:
            idx = min(len(session.snapshots) - 1, steps)

        snapshot = session.snapshots[idx]
        return {
            "operation": "time_travel",
            "direction": direction,
            "steps": steps,
            "snapshot": snapshot.name,
            "timestamp": snapshot.timestamp.isoformat(),
            "frame": snapshot.frame_id,
        }

    def inspect(self, expression: str) -> dict:
        """Inspecciona expresion."""
        session = self.get_current_session()
        if not session:
            return {"error": "No active session"}

        # Simular evaluacion (en produccion: evaluar en contexto)
        simulated_values = {
            "x": 42,
            "user": {"name": "test", "id": 1},
            "items": [1, 2, 3],
            "len(items)": 3,
            "user.name": "test",
        }

        value = simulated_values.get(expression, f"<unknown: {expression}>")

        return {
            "operation": "inspect",
            "expression": expression,
            "value": value,
            "type": type(value).__name__,
        }

    def evaluate(self, expression: str) -> dict:
        """Evalua expresion en contexto."""
        session = self.get_current_session()
        if not session:
            return {"error": "No active session"}

        # Simular evaluacion
        try:
            # En produccion: evaluar en el contexto del debugger
            if expression.isdigit():
                result = int(expression)
            elif "+" in expression or "-" in expression:
                result = ast.literal_eval(expression)  # Seguro: solo literales
            else:
                result = f"<evaluated: {expression}>"

            return {
                "operation": "evaluate",
                "expression": expression,
                "result": result,
                "type": type(result).__name__,
            }
        except Exception as e:
            return {"operation": "evaluate", "expression": expression, "error": str(e)}

    def analyze_error(self, error_info: str) -> dict:
        """Analiza error y sugiere causas."""
        # Patrones comunes de errores
        suggestions = []

        error_lower = error_info.lower()

        if "typeerror" in error_lower:
            suggestions.append("Check variable types before operations")
            suggestions.append("Verify function arguments match expected types")
            if "nonetype" in error_lower:
                suggestions.append("A variable is None when it shouldn't be")
                suggestions.append("Check if function returns None unexpectedly")

        elif "keyerror" in error_lower:
            suggestions.append("Dictionary key does not exist")
            suggestions.append("Use .get() with default value")
            suggestions.append("Check if key is spelled correctly")

        elif "indexerror" in error_lower:
            suggestions.append("List/array index out of bounds")
            suggestions.append("Check list length before accessing")
            suggestions.append("Verify loop bounds")

        elif "attributeerror" in error_lower:
            suggestions.append("Object doesn't have the attribute")
            suggestions.append("Check object type with type() or isinstance()")
            suggestions.append("Verify import statements")

        elif "importerror" in error_lower or "modulenotfounderror" in error_lower:
            suggestions.append("Module not installed or wrong name")
            suggestions.append("Check virtual environment")
            suggestions.append("Verify PYTHONPATH")

        else:
            suggestions.append("Set breakpoint before error location")
            suggestions.append("Inspect variable values")
            suggestions.append("Check recent changes")

        return {
            "operation": "analyze",
            "error": error_info[:100],
            "suggestions": suggestions,
            "recommended_actions": [
                "Set breakpoint at error location",
                "Take snapshot before error",
                "Inspect related variables",
            ],
        }

    def execute(self, command: str) -> dict:
        """Ejecuta comando de debug."""
        parts = command.strip().split(None, 1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "start":
            target = args or "app.py"
            session = self.start_session(target)
            return {
                "operation": "start",
                "session_id": session.id,
                "target": session.target,
                "status": session.status.value,
            }

        elif cmd == "break":
            # Format: break file.py:42 [condition]
            match = args.split(":")
            if len(match) >= 2:
                file = match[0]
                rest = match[1].split(None, 1)
                line = int(rest[0])
                condition = rest[1] if len(rest) > 1 else None

                try:
                    bp = self.add_breakpoint(file, line, condition)
                    return {
                        "operation": "breakpoint",
                        "id": bp.id,
                        "file": bp.file,
                        "line": bp.line,
                        "condition": bp.condition,
                    }
                except ValueError as e:
                    return {"error": str(e)}

            return {"error": "Usage: break file.py:line [condition]"}

        elif cmd == "watch":
            try:
                wp = self.add_watchpoint(args)
                return {"operation": "watchpoint", "id": wp.id, "expression": wp.expression}
            except ValueError as e:
                return {"error": str(e)}

        elif cmd == "snapshot":
            try:
                snap = self.take_snapshot(args if args else None)
                return {
                    "operation": "snapshot",
                    "id": snap.id,
                    "name": snap.name,
                    "timestamp": snap.timestamp.isoformat(),
                }
            except ValueError as e:
                return {"error": str(e)}

        elif cmd == "back":
            steps = int(args) if args.isdigit() else 1
            return self.time_travel("back", steps)

        elif cmd == "forward":
            steps = int(args) if args.isdigit() else 1
            return self.time_travel("forward", steps)

        elif cmd == "inspect":
            return self.inspect(args)

        elif cmd == "eval":
            return self.evaluate(args)

        elif cmd == "analyze":
            return self.analyze_error(args)

        elif cmd == "status":
            session = self.get_current_session()
            if session:
                return {
                    "operation": "status",
                    "session_id": session.id,
                    "target": session.target,
                    "status": session.status.value,
                    "breakpoints": len(session.breakpoints),
                    "watchpoints": len(session.watchpoints),
                    "snapshots": len(session.snapshots),
                }
            return {"error": "No active session"}

        else:
            return {
                "operation": "help",
                "commands": {
                    "start <target>": "Start debug session",
                    "break file:line [cond]": "Set breakpoint",
                    "watch <expr>": "Watch expression",
                    "snapshot [name]": "Take state snapshot",
                    "back [n]": "Time travel back n steps",
                    "forward [n]": "Time travel forward n steps",
                    "inspect <expr>": "Inspect expression value",
                    "eval <expr>": "Evaluate expression",
                    "analyze <error>": "Analyze error",
                    "status": "Show session status",
                },
            }


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Debugger - Debug interactivo avanzado"
    )
    parser.add_argument("command", nargs="?", default="status", help="Comando de debug")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    debugger = InteractiveDebugger()

    # Iniciar sesion demo
    debugger.start_session("demo.py")
    debugger.add_breakpoint("demo.py", 10)
    debugger.take_snapshot("initial")

    result = debugger.execute(args.command)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        op = result.get("operation", "unknown")

        if op == "help":
            print("Interactive Debugger Commands")
            print("=" * 40)
            for cmd, desc in result.get("commands", {}).items():
                print(f"  {cmd:25} {desc}")

        elif op == "status":
            print(f"Debug Session: {result.get('session_id', 'none')}")
            print(f"Target: {result.get('target', 'none')}")
            print(f"Status: {result.get('status', 'unknown')}")
            print(f"Breakpoints: {result.get('breakpoints', 0)}")
            print(f"Watchpoints: {result.get('watchpoints', 0)}")
            print(f"Snapshots: {result.get('snapshots', 0)}")

        elif op == "analyze":
            print(f"Error Analysis: {result.get('error', '')[:50]}...")
            print("\nSuggestions:")
            for s in result.get("suggestions", []):
                print(f"  - {s}")
            print("\nRecommended actions:")
            for a in result.get("recommended_actions", []):
                print(f"  > {a}")

        elif "error" in result:
            print(f"Error: {result['error']}")

        else:
            for key, value in result.items():
                print(f"{key}: {value}")

    sys.exit(0)


if __name__ == "__main__":
    main()
