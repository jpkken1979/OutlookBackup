"""
Agent Contracts — SLA & Accountability.

Sistema de contratos de rendimiento para agentes:
  - Cada agente puede firmar un contrato (SLA)
  - El contrato define: max_response_time, min_success_rate, domains
  - El sistema monitorea cumplimiento en tiempo real
  - Violaciones generan alertas y bajan reputación
  - Contratos pueden ser auto-generados basados en historial
  - Escalación automática ante incumplimiento reiterado

Usage:
    contracts = ContractManager(bus=bus)

    # Crear contrato
    contract = contracts.create_contract(
        agent="explorer",
        max_response_time=10.0,
        min_success_rate=0.85,
        domains=["code_analysis", "architecture"],
    )

    # Registrar ejecución
    contracts.record_execution(
        agent="explorer",
        duration=2.5,
        success=True,
        domain="code_analysis",
    )

    # Verificar cumplimiento
    compliance = contracts.check_compliance("explorer")

    # Auto-generar contrato basado en historial
    auto = contracts.auto_generate_contract("explorer")
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.agent_contracts")

# ============================================================
# Constantes
# ============================================================
DEFAULT_MAX_RESPONSE_TIME = 30.0  # Segundos
DEFAULT_MIN_SUCCESS_RATE = 0.75  # 75%
VIOLATION_GRACE_PERIOD = 3  # Violaciones antes de escalación
COMPLIANCE_WINDOW = 50  # Últimas N ejecuciones para medir
MAX_EXECUTION_HISTORY = 500  # Máximo de registros por agente
ESCALATION_COOLDOWN = 300.0  # 5 min entre escalaciones


# ============================================================
# Enums
# ============================================================
class ContractStatus(str, Enum):
    """Estados del contrato."""

    ACTIVE = "active"
    SUSPENDED = "suspended"  # Suspendido por violaciones
    EXPIRED = "expired"
    DRAFT = "draft"


class ViolationType(str, Enum):
    """Tipos de violación."""

    RESPONSE_TIME = "response_time"
    SUCCESS_RATE = "success_rate"
    AVAILABILITY = "availability"


class EscalationLevel(str, Enum):
    """Niveles de escalación."""

    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"
    SUSPENSION = "suspension"


# ============================================================
# Modelos
# ============================================================
@dataclass
class ExecutionRecord:
    """Registro de una ejecución."""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    domain: str = "general"
    duration: float = 0.0
    success: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "agent": self.agent,
            "domain": self.domain,
            "duration": round(self.duration, 3),
            "success": self.success,
            "timestamp": self.timestamp,
        }


@dataclass
class Violation:
    """Registro de una violación de contrato."""

    violation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    violation_type: ViolationType = ViolationType.RESPONSE_TIME
    detail: str = ""
    severity: EscalationLevel = EscalationLevel.WARNING
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "agent": self.agent,
            "violation_type": self.violation_type.value,
            "detail": self.detail,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
        }


@dataclass
class Contract:
    """Contrato SLA de un agente."""

    contract_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    status: ContractStatus = ContractStatus.ACTIVE

    # SLA parameters
    max_response_time: float = DEFAULT_MAX_RESPONSE_TIME
    min_success_rate: float = DEFAULT_MIN_SUCCESS_RATE
    domains: list[str] = field(default_factory=list)

    # Tracking
    executions: list[ExecutionRecord] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_checked: float = field(default_factory=time.time)
    last_escalation: float = 0.0

    @property
    def total_executions(self) -> int:
        return len(self.executions)

    @property
    def recent_executions(self) -> list[ExecutionRecord]:
        """Últimas N ejecuciones dentro de la ventana."""
        return self.executions[-COMPLIANCE_WINDOW:]

    @property
    def current_success_rate(self) -> float:
        """Tasa de éxito actual."""
        recent = self.recent_executions
        if not recent:
            return 1.0
        successes = sum(1 for e in recent if e.success)
        return successes / len(recent)

    @property
    def current_avg_response(self) -> float:
        """Tiempo de respuesta promedio actual."""
        recent = self.recent_executions
        if not recent:
            return 0.0
        return sum(e.duration for e in recent) / len(recent)

    @property
    def is_compliant(self) -> bool:
        """Si el contrato está en cumplimiento."""
        if self.status != ContractStatus.ACTIVE:
            return False
        if len(self.recent_executions) < 3:
            return True  # Not enough data
        return (
            self.current_success_rate >= self.min_success_rate
            and self.current_avg_response <= self.max_response_time
        )

    @property
    def violation_count(self) -> int:
        """Violaciones recientes (last 1 hour)."""
        cutoff = time.time() - 3600
        return sum(1 for v in self.violations if v.timestamp > cutoff)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "agent": self.agent,
            "status": self.status.value,
            "max_response_time": self.max_response_time,
            "min_success_rate": self.min_success_rate,
            "domains": self.domains,
            "total_executions": self.total_executions,
            "current_success_rate": round(self.current_success_rate, 3),
            "current_avg_response": round(self.current_avg_response, 3),
            "is_compliant": self.is_compliant,
            "violations_recent": self.violation_count,
            "violations_total": len(self.violations),
            "created_at": self.created_at,
        }


# ============================================================
# Contract Manager
# ============================================================
class ContractManager:
    """
    Gestiona contratos SLA para agentes.
    Monitorea cumplimiento, detecta violaciones, escala.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._contracts: dict[str, Contract] = {}

        # Métricas
        self._metrics = {
            "contracts_created": 0,
            "executions_recorded": 0,
            "violations_detected": 0,
            "escalations_triggered": 0,
            "contracts_suspended": 0,
            "auto_contracts_generated": 0,
        }

    # --------------------------------------------------------
    # Create Contract
    # --------------------------------------------------------
    def create_contract(
        self,
        agent: str,
        max_response_time: float = DEFAULT_MAX_RESPONSE_TIME,
        min_success_rate: float = DEFAULT_MIN_SUCCESS_RATE,
        domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Crea un contrato SLA para un agente.

        Args:
            agent: Nombre del agente.
            max_response_time: Máximo tiempo de respuesta (segundos).
            min_success_rate: Mínima tasa de éxito [0, 1].
            domains: Dominios cubiertos.

        Returns:
            El contrato creado.
        """
        contract = Contract(
            agent=agent,
            max_response_time=max(1.0, max_response_time),
            min_success_rate=max(0.0, min(1.0, min_success_rate)),
            domains=domains or [],
        )
        self._contracts[agent] = contract
        self._metrics["contracts_created"] += 1

        logger.info(
            "Contract created for %s: response<%.1fs, success>=%.0f%%",
            agent,
            contract.max_response_time,
            contract.min_success_rate * 100,
        )

        return contract.to_dict()

    # --------------------------------------------------------
    # Record Execution
    # --------------------------------------------------------
    def record_execution(
        self,
        agent: str,
        duration: float = 0.0,
        success: bool = True,
        domain: str = "general",
    ) -> dict[str, Any] | None:
        """
        Registra una ejecución y verifica cumplimiento.

        Returns:
            Violation dict si hubo violación, None si todo ok.
        """
        contract = self._contracts.get(agent)
        if not contract or contract.status != ContractStatus.ACTIVE:
            return None

        record = ExecutionRecord(
            agent=agent,
            domain=domain,
            duration=duration,
            success=success,
        )
        contract.executions.append(record)

        # Limit history
        if len(contract.executions) > MAX_EXECUTION_HISTORY:
            contract.executions = contract.executions[-MAX_EXECUTION_HISTORY:]

        self._metrics["executions_recorded"] += 1

        # Check for violations
        violation = self._check_violations(contract, record)
        return violation

    # --------------------------------------------------------
    # Compliance Check
    # --------------------------------------------------------
    def check_compliance(self, agent: str) -> dict[str, Any]:
        """Verifica el cumplimiento de un contrato."""
        contract = self._contracts.get(agent)
        if not contract:
            return {"agent": agent, "status": "no_contract"}

        contract.last_checked = time.time()

        issues = []
        if contract.current_success_rate < contract.min_success_rate:
            issues.append(
                {
                    "type": "success_rate",
                    "required": contract.min_success_rate,
                    "actual": round(contract.current_success_rate, 3),
                    "gap": round(contract.min_success_rate - contract.current_success_rate, 3),
                }
            )

        if contract.current_avg_response > contract.max_response_time:
            issues.append(
                {
                    "type": "response_time",
                    "max_allowed": contract.max_response_time,
                    "actual": round(contract.current_avg_response, 3),
                    "excess": round(
                        contract.current_avg_response - contract.max_response_time,
                        3,
                    ),
                }
            )

        return {
            "agent": agent,
            "is_compliant": contract.is_compliant,
            "contract_status": contract.status.value,
            "success_rate": round(contract.current_success_rate, 3),
            "avg_response": round(contract.current_avg_response, 3),
            "violations_recent": contract.violation_count,
            "issues": issues,
        }

    def check_all_compliance(self) -> list[dict[str, Any]]:
        """Verifica cumplimiento de todos los contratos."""
        return [self.check_compliance(agent) for agent in self._contracts]

    # --------------------------------------------------------
    # Auto-Generate Contract
    # --------------------------------------------------------
    def auto_generate_contract(
        self,
        agent: str,
        executions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Auto-genera un contrato basado en rendimiento histórico.

        Si el agente ya tiene ejecuciones registradas, usa esas.
        Si se pasan ejecuciones externas, las usa como base.
        """
        existing = self._contracts.get(agent)
        records = []

        if executions:
            records = executions
        elif existing and existing.executions:
            records = [e.to_dict() for e in existing.executions]

        if not records:
            # Default contract si no hay datos
            return self.create_contract(agent)

        # Calcular SLA basado en historial
        durations = [r.get("duration", r.get("duration", 0)) for r in records]
        successes = sum(1 for r in records if r.get("success", True))

        avg_duration = sum(durations) / len(durations) if durations else 10.0
        success_rate = successes / len(records) if records else 0.8

        # SLA = histórico con 20% de margen
        max_response = round(avg_duration * 1.2, 1)
        min_success = round(max(0.5, success_rate - 0.1), 2)

        self._metrics["auto_contracts_generated"] += 1

        return self.create_contract(
            agent=agent,
            max_response_time=max_response,
            min_success_rate=min_success,
        )

    # --------------------------------------------------------
    # Contract Management
    # --------------------------------------------------------
    def get_contract(self, agent: str) -> dict[str, Any] | None:
        """Obtiene un contrato."""
        contract = self._contracts.get(agent)
        return contract.to_dict() if contract else None

    def list_contracts(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista contratos, opcionalmente filtrados por status."""
        contracts = list(self._contracts.values())
        if status:
            contracts = [c for c in contracts if c.status.value == status]
        return [c.to_dict() for c in contracts]

    def suspend_contract(self, agent: str, reason: str = "") -> dict[str, Any] | None:
        """Suspende un contrato."""
        contract = self._contracts.get(agent)
        if not contract:
            return None
        contract.status = ContractStatus.SUSPENDED
        self._metrics["contracts_suspended"] += 1
        logger.warning("Contract suspended for %s: %s", agent, reason)
        return contract.to_dict()

    def reactivate_contract(self, agent: str) -> dict[str, Any] | None:
        """Reactiva un contrato suspendido."""
        contract = self._contracts.get(agent)
        if not contract:
            return None
        contract.status = ContractStatus.ACTIVE
        contract.violations = []  # Reset violations on reactivation
        return contract.to_dict()

    def delete_contract(self, agent: str) -> bool:
        """Elimina un contrato."""
        if agent in self._contracts:
            del self._contracts[agent]
            return True
        return False

    # --------------------------------------------------------
    # Violations & Escalation
    # --------------------------------------------------------
    def get_violations(
        self,
        agent: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista violaciones filtradas."""
        violations = []
        for contract in self._contracts.values():
            if agent and contract.agent != agent:
                continue
            for v in contract.violations:
                if severity and v.severity.value != severity:
                    continue
                violations.append(v.to_dict())

        violations.sort(key=lambda v: v["timestamp"], reverse=True)
        return violations[:limit]

    def get_non_compliant_agents(self) -> list[dict[str, Any]]:
        """Retorna agentes que no cumplen su SLA."""
        return [
            self.check_compliance(agent)
            for agent, contract in self._contracts.items()
            if not contract.is_compliant
        ]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de contratos."""
        active = sum(1 for c in self._contracts.values() if c.status == ContractStatus.ACTIVE)
        suspended = sum(1 for c in self._contracts.values() if c.status == ContractStatus.SUSPENDED)
        compliant = sum(1 for c in self._contracts.values() if c.is_compliant)

        return {
            "total_contracts": len(self._contracts),
            "active": active,
            "suspended": suspended,
            "compliant": compliant,
            "non_compliant": active - compliant,
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _check_violations(
        self,
        contract: Contract,
        record: ExecutionRecord,
    ) -> dict[str, Any] | None:
        """Verifica si la ejecución viola el contrato."""
        violation = None

        # Check response time
        if record.duration > contract.max_response_time:
            violation = Violation(
                agent=contract.agent,
                violation_type=ViolationType.RESPONSE_TIME,
                detail=(
                    f"duration={record.duration:.1f}s exceeds max={contract.max_response_time:.1f}s"
                ),
            )
            contract.violations.append(violation)
            self._metrics["violations_detected"] += 1

        # Check success rate (after enough data)
        if len(contract.recent_executions) >= 5:
            if contract.current_success_rate < contract.min_success_rate:
                if not violation:  # Don't double-count
                    violation = Violation(
                        agent=contract.agent,
                        violation_type=ViolationType.SUCCESS_RATE,
                        detail=(
                            f"rate={contract.current_success_rate:.2f} "
                            f"below min={contract.min_success_rate:.2f}"
                        ),
                    )
                    contract.violations.append(violation)
                    self._metrics["violations_detected"] += 1

        # Check escalation
        if contract.violation_count >= VIOLATION_GRACE_PERIOD:
            self._escalate(contract)

        return violation.to_dict() if violation else None

    def _escalate(self, contract: Contract) -> None:
        """Escala según el número de violaciones."""
        now = time.time()
        if now - contract.last_escalation < ESCALATION_COOLDOWN:
            return  # Cooldown

        count = contract.violation_count
        if count >= VIOLATION_GRACE_PERIOD * 3:
            level = EscalationLevel.SUSPENSION
            contract.status = ContractStatus.SUSPENDED
            self._metrics["contracts_suspended"] += 1
        elif count >= VIOLATION_GRACE_PERIOD * 2:
            level = EscalationLevel.CRITICAL
        elif count >= VIOLATION_GRACE_PERIOD:
            level = EscalationLevel.ALERT
        else:
            level = EscalationLevel.WARNING

        contract.last_escalation = now
        self._metrics["escalations_triggered"] += 1

        # Update severity of recent violations
        for v in contract.violations[-3:]:
            v.severity = level

        logger.warning(
            "Escalation %s for %s: %d violations",
            level.value,
            contract.agent,
            count,
        )


# ============================================================
# Singleton
# ============================================================
_instance: ContractManager | None = None


def get_contract_manager(bus: Any = None) -> ContractManager:
    """Obtiene o crea el contract manager global."""
    global _instance
    if _instance is None:
        _instance = ContractManager(bus=bus)
    return _instance
