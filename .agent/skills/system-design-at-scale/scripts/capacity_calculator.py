#!/usr/bin/env python3
"""
System Design at Scale - Calculadora de Capacidad
Herramientas para estimación de capacidad en sistemas a escala.
"""

import logging
from dataclasses import dataclass
from enum import Enum
import math

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS - Latency Numbers Every Programmer Should Know
# =============================================================================


class LatencyNumbers:
    """Números de latencia que todo programador debe conocer (2024)."""

    L1_CACHE_REF = 0.5  # ns
    BRANCH_MISPREDICT = 5  # ns
    L2_CACHE_REF = 7  # ns
    MUTEX_LOCK = 25  # ns
    MAIN_MEMORY_REF = 100  # ns
    COMPRESS_1KB_ZIPPY = 3_000  # ns
    SEND_1KB_OVER_1GBPS = 10_000  # ns
    READ_4KB_SSD = 150_000  # ns
    READ_1MB_SSD = 1_000_000  # ns (1 ms)
    ROUND_TRIP_SAME_DC = 500_000  # ns (0.5 ms)
    READ_1MB_HDD = 20_000_000  # ns (20 ms)
    ROUND_TRIP_CROSS_CONTINENT = 150_000_000  # ns (150 ms)

    @classmethod
    def display(cls) -> str:
        """Muestra tabla de latencias."""
        lines = [
            "LATENCY NUMBERS (2024)",
            "-" * 50,
            f"L1 cache reference:          {cls.L1_CACHE_REF} ns",
            f"Branch mispredict:           {cls.BRANCH_MISPREDICT} ns",
            f"L2 cache reference:          {cls.L2_CACHE_REF} ns",
            f"Mutex lock/unlock:           {cls.MUTEX_LOCK} ns",
            f"Main memory reference:       {cls.MAIN_MEMORY_REF} ns",
            f"Compress 1KB with Zippy:     {cls.COMPRESS_1KB_ZIPPY:,} ns (3 us)",
            f"Send 1KB over 1 Gbps:        {cls.SEND_1KB_OVER_1GBPS:,} ns (10 us)",
            f"Read 4KB from SSD:           {cls.READ_4KB_SSD:,} ns (150 us)",
            f"Read 1MB from SSD:           {cls.READ_1MB_SSD:,} ns (1 ms)",
            f"Round trip same datacenter:  {cls.ROUND_TRIP_SAME_DC:,} ns (0.5 ms)",
            f"Read 1MB from HDD:           {cls.READ_1MB_HDD:,} ns (20 ms)",
            f"Round trip cross-continent:  {cls.ROUND_TRIP_CROSS_CONTINENT:,} ns (150 ms)",
        ]
        return "\n".join(lines)


# =============================================================================
# CAPACITY ESTIMATION
# =============================================================================


class DataUnit(Enum):
    BYTES = 1
    KB = 1024
    MB = 1024**2
    GB = 1024**3
    TB = 1024**4
    PB = 1024**5


@dataclass
class TrafficEstimate:
    """Estimación de tráfico."""

    daily_active_users: int
    actions_per_user_per_day: float
    avg_request_size_bytes: int
    avg_response_size_bytes: int
    read_write_ratio: float = 100.0  # reads per write

    @property
    def daily_requests(self) -> int:
        return int(self.daily_active_users * self.actions_per_user_per_day)

    @property
    def requests_per_second(self) -> float:
        return self.daily_requests / (24 * 3600)

    @property
    def peak_qps(self) -> float:
        """Peak QPS (asumiendo 2x del promedio)."""
        return self.requests_per_second * 2

    @property
    def daily_data_in_bytes(self) -> int:
        return self.daily_requests * (self.avg_request_size_bytes + self.avg_response_size_bytes)

    @property
    def bandwidth_mbps(self) -> float:
        bytes_per_second = self.daily_data_in_bytes / (24 * 3600)
        return (bytes_per_second * 8) / (1024 * 1024)


@dataclass
class StorageEstimate:
    """Estimación de almacenamiento."""

    daily_new_records: int
    avg_record_size_bytes: int
    retention_years: int = 5
    replication_factor: int = 3

    @property
    def daily_storage_bytes(self) -> int:
        return self.daily_new_records * self.avg_record_size_bytes

    @property
    def yearly_storage_bytes(self) -> int:
        return self.daily_storage_bytes * 365

    @property
    def total_storage_bytes(self) -> int:
        return self.yearly_storage_bytes * self.retention_years

    @property
    def total_with_replication_bytes(self) -> int:
        return self.total_storage_bytes * self.replication_factor

    def format_storage(self, bytes_val: int) -> str:
        """Formatea bytes a unidad legible."""
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} PB"


@dataclass
class CacheEstimate:
    """Estimación de caché."""

    daily_requests: int
    cache_hit_ratio: float = 0.8
    avg_cached_item_size_bytes: int = 1024
    unique_items_ratio: float = 0.2  # % de items únicos

    @property
    def cache_hits_per_day(self) -> int:
        return int(self.daily_requests * self.cache_hit_ratio)

    @property
    def cache_misses_per_day(self) -> int:
        return int(self.daily_requests * (1 - self.cache_hit_ratio))

    @property
    def estimated_cache_size_bytes(self) -> int:
        unique_items = int(self.daily_requests * self.unique_items_ratio)
        return unique_items * self.avg_cached_item_size_bytes


class CapacityCalculator:
    """Calculadora de capacidad para system design."""

    def __init__(self) -> None:
        self.traffic: TrafficEstimate | None = None
        self.storage: StorageEstimate | None = None
        self.cache: CacheEstimate | None = None

    def estimate_traffic(
        self,
        daily_active_users: int,
        actions_per_user: float = 10,
        request_size: int = 500,
        response_size: int = 2000,
        read_write_ratio: float = 100,
    ) -> TrafficEstimate:
        """Estima tráfico del sistema."""
        self.traffic = TrafficEstimate(
            daily_active_users=daily_active_users,
            actions_per_user_per_day=actions_per_user,
            avg_request_size_bytes=request_size,
            avg_response_size_bytes=response_size,
            read_write_ratio=read_write_ratio,
        )
        return self.traffic

    def estimate_storage(
        self,
        daily_new_records: int,
        record_size: int = 1000,
        retention_years: int = 5,
        replication: int = 3,
    ) -> StorageEstimate:
        """Estima almacenamiento necesario."""
        self.storage = StorageEstimate(
            daily_new_records=daily_new_records,
            avg_record_size_bytes=record_size,
            retention_years=retention_years,
            replication_factor=replication,
        )
        return self.storage

    def estimate_cache(
        self, cache_hit_ratio: float = 0.8, item_size: int = 1024, unique_ratio: float = 0.2
    ) -> CacheEstimate:
        """Estima tamaño de caché necesario."""
        if not self.traffic:
            raise ValueError("Calculate traffic estimate first")

        self.cache = CacheEstimate(
            daily_requests=self.traffic.daily_requests,
            cache_hit_ratio=cache_hit_ratio,
            avg_cached_item_size_bytes=item_size,
            unique_items_ratio=unique_ratio,
        )
        return self.cache

    def estimate_servers(self, qps_per_server: int = 1000, memory_per_server_gb: int = 64) -> dict:
        """Estima número de servidores necesarios."""
        if not self.traffic:
            raise ValueError("Calculate traffic estimate first")

        # Servidores por QPS
        servers_for_qps = math.ceil(self.traffic.peak_qps / qps_per_server)

        # Servidores por memoria (si hay caché)
        servers_for_memory = 1
        if self.cache:
            cache_gb = self.cache.estimated_cache_size_bytes / (1024**3)
            servers_for_memory = math.ceil(cache_gb / memory_per_server_gb)

        return {
            "by_qps": servers_for_qps,
            "by_memory": servers_for_memory,
            "recommended": max(servers_for_qps, servers_for_memory, 3),  # min 3 for HA
            "qps_per_server": qps_per_server,
            "memory_per_server_gb": memory_per_server_gb,
        }

    def generate_report(self) -> str:
        """Genera reporte completo de capacidad."""
        lines = [
            "=" * 60,
            "SYSTEM DESIGN - CAPACITY ESTIMATION REPORT",
            "=" * 60,
        ]

        if self.traffic:
            lines.extend(
                [
                    "",
                    "TRAFFIC ESTIMATES:",
                    f"  Daily Active Users:     {self.traffic.daily_active_users:,}",
                    f"  Actions per User/Day:   {self.traffic.actions_per_user_per_day}",
                    f"  Daily Requests:         {self.traffic.daily_requests:,}",
                    f"  Requests per Second:    {self.traffic.requests_per_second:,.2f}",
                    f"  Peak QPS (2x):          {self.traffic.peak_qps:,.2f}",
                    f"  Read/Write Ratio:       {self.traffic.read_write_ratio}:1",
                    f"  Bandwidth:              {self.traffic.bandwidth_mbps:,.2f} Mbps",
                ]
            )

        if self.storage:
            lines.extend(
                [
                    "",
                    "STORAGE ESTIMATES:",
                    f"  Daily New Records:      {self.storage.daily_new_records:,}",
                    f"  Avg Record Size:        {self.storage.avg_record_size_bytes:,} bytes",
                    f"  Retention:              {self.storage.retention_years} years",
                    f"  Replication Factor:     {self.storage.replication_factor}x",
                    f"  Daily Storage:          {self.storage.format_storage(self.storage.daily_storage_bytes)}",
                    f"  Yearly Storage:         {self.storage.format_storage(self.storage.yearly_storage_bytes)}",
                    f"  Total Storage:          {self.storage.format_storage(self.storage.total_storage_bytes)}",
                    f"  With Replication:       {self.storage.format_storage(self.storage.total_with_replication_bytes)}",
                ]
            )

        if self.cache:
            lines.extend(
                [
                    "",
                    "CACHE ESTIMATES:",
                    f"  Cache Hit Ratio:        {self.cache.cache_hit_ratio * 100:.0f}%",
                    f"  Daily Cache Hits:       {self.cache.cache_hits_per_day:,}",
                    f"  Daily Cache Misses:     {self.cache.cache_misses_per_day:,}",
                    f"  Estimated Cache Size:   {self.storage.format_storage(self.cache.estimated_cache_size_bytes) if self.storage else 'N/A'}",
                ]
            )

        if self.traffic:
            servers = self.estimate_servers()
            lines.extend(
                [
                    "",
                    "SERVER ESTIMATES:",
                    f"  Servers by QPS:         {servers['by_qps']}",
                    f"  Servers by Memory:      {servers['by_memory']}",
                    f"  Recommended (HA):       {servers['recommended']}",
                ]
            )

        lines.extend(
            [
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)


# =============================================================================
# DEMO
# =============================================================================


def main() -> None:
    """Demostración de cálculos de capacidad."""
    print("\n" + "=" * 60)
    print("SYSTEM DESIGN AT SCALE - Capacity Calculator")
    print("=" * 60)

    # Mostrar latencias
    print("\n" + LatencyNumbers.display())

    # Ejemplo: Twitter-like service
    print("\n\n--- EXAMPLE: Twitter-like Service ---")

    calc = CapacityCalculator()

    # Traffic: 500M DAU, 10 tweets viewed per user, 5 tweets posted
    calc.estimate_traffic(
        daily_active_users=500_000_000,
        actions_per_user=15,  # views + posts
        request_size=500,
        response_size=2000,
        read_write_ratio=100,  # 100 reads per 1 write
    )

    # Storage: 100M new tweets/day, 280 chars avg
    calc.estimate_storage(
        daily_new_records=100_000_000,
        record_size=500,  # tweet + metadata
        retention_years=5,
        replication=3,
    )

    # Cache: 80% hit ratio for timeline
    calc.estimate_cache(
        cache_hit_ratio=0.8,
        item_size=2000,  # cached tweet
        unique_ratio=0.1,
    )

    print(calc.generate_report())

    # Ejemplo: URL Shortener
    print("\n--- EXAMPLE: URL Shortener ---")

    calc2 = CapacityCalculator()

    calc2.estimate_traffic(
        daily_active_users=100_000_000,
        actions_per_user=1,  # 1 redirect per user
        request_size=100,
        response_size=300,
        read_write_ratio=1000,  # mostly reads
    )

    calc2.estimate_storage(
        daily_new_records=1_000_000,  # 1M new URLs/day
        record_size=200,  # short URL + long URL + metadata
        retention_years=10,
        replication=3,
    )

    calc2.estimate_cache(
        cache_hit_ratio=0.9,  # high cache hit for popular URLs
        item_size=200,
        unique_ratio=0.05,  # 5% unique URLs accessed daily
    )

    print(calc2.generate_report())


if __name__ == "__main__":
    main()
