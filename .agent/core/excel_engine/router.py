"""BackendRouter — decision table that selects Backend per operation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from excel_engine.types import Backend, SessionState

logger = logging.getLogger(__name__)

# Operations supported by the engine.
KNOWN_OPS: frozenset[str] = frozenset(
    {
        "open",
        "close",
        "list_sessions",
        "parse_smart",
        "read_range",
        "write_range",
        "apply_formula",
        "set_format",
        "create_table",
        "create_chart",
        "create_pivot",
        "run_macro",
        "update_dashboard",
        "screenshot",
        "power_query",
        "dax_measure",
        "slicer",
        "conditional_format",
        "calculation_mode",
        "save_as",
    }
)

# Operations that strictly require xlwings (live Excel).
XLWINGS_REQUIRED: frozenset[str] = frozenset(
    {
        "run_macro",
        "create_chart",
        "create_pivot",
        "update_dashboard",
        "screenshot",
        "power_query",
        "dax_measure",
        "slicer",
        "conditional_format",
        "calculation_mode",
    }
)


class BackendUnavailable(Exception):
    """Raised when the chosen backend is not available in current env."""


@dataclass
class RouterEnv:
    """Environment snapshot consulted by the router."""

    excel_running: bool = False
    can_launch_excel: bool = False


class BackendRouter:
    """Decides which Backend executes a given operation.

    Decision order:
        1. parse_smart → SUPER_AGENT
        2. op in XLWINGS_REQUIRED → XLWINGS (or BackendUnavailable)
        3. session.opened_with == XLWINGS → XLWINGS (consistency)
        4. session.mode == "live" → XLWINGS
        5. default → OPENPYXL
    """

    def choose(
        self,
        op: str,
        session: SessionState,
        env: RouterEnv,
    ) -> Backend:
        """Return the Backend chosen for this op + session + env.

        Args:
            op: Operation name. Must be in KNOWN_OPS.
            session: Current session state.
            env: Environment snapshot (Excel running, can launch, etc.).

        Returns:
            The Backend that should handle this operation.

        Raises:
            ValueError: If op is not in KNOWN_OPS.
            BackendUnavailable: If op requires xlwings but Excel is not available.
        """
        if op not in KNOWN_OPS:
            raise ValueError(f"unknown op: {op!r}")

        # 1. Lectura compleja siempre va al super-agent
        if op == "parse_smart":
            return Backend.SUPER_AGENT

        # 2. Operaciones que SOLO funcionan con Excel vivo
        if op in XLWINGS_REQUIRED:
            if not env.excel_running and not env.can_launch_excel:
                raise BackendUnavailable(
                    f"op={op!r} requires xlwings; Excel not running and headless mode"
                )
            return Backend.XLWINGS

        # 3. Sesion ya abierta con xlwings, mantener consistencia
        if session.opened_with == Backend.XLWINGS:
            return Backend.XLWINGS

        # 4. Modo live pedido al open
        if session.mode == "live":
            return Backend.XLWINGS

        # 5. Default: openpyxl
        return Backend.OPENPYXL
